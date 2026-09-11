"""Production durability, aggregation, and result persistence for the frozen harness.

This layer sits above frozen scientific primitives. It does not change RNG, DGP,
gates, Wilson, taxonomy, or mechanical-conclusion semantics. It does not weaken
FixtureExecutionConfig.

The canonical 3200-world driver exists in this module. A performance-only
descendant may cache BASE placebo predictions, use lstsq rank, and evaluate
independent worlds in parallel. Those changes do not authorize production:
the unused ARM at freeze-parent child 0abc5fe remains unused and does not
authorize this HEAD. A later independent review plus a NEW ARM is required
before any production execution. Canonical execution, when later armed,
must cross a fresh Python interpreter boundary and re-verify exact HEAD/tree
plus execution-authority bytes inside that process.
Final RESULT minting requires an unforgeable in-process canonical session
capability; caller-supplied records cannot mint.

Run identity is a pure function of tracked authority at the exact execution
commit. Local untracked reservation files cannot mint a distinct run/result.
This module does not claim global process exclusion.

RESULT verification has two distinct authority models:
- LIVE / execution-context: `verify_bound_result_document` re-derives the
  expected core from current HEAD, worktree, and caller-supplied records.
- TRACKED / historical: `verify_bound_result_from_tracked_authority` reads
  `execution_head` from the RESULT core itself, loads authority from git
  objects at that exact commit, and re-verifies ARM topology at execution
  time. Production WORLD_RECORDS are retained evidence, not self-authenticating
  authority. Authoritative historical verification of a production RESULT
  crosses a fresh isolated interpreter (`HISTORICAL_RECOMPUTE_MODE`) using
  the existing `#115` bootstrap. That child independently proves executing
  scientific/production blobs match `execution_head`, derives the frozen plan
  internally, recomputes all 3200 worlds, compares canonical WORLD_RECORDS
  evidence, then recomputes RESULT science. The parent treats the child's
  success proof as the recomputation result and does not re-run or override
  science in-process. There is no in-process fallback. Spot-checks cannot mint
  or validate durable claims. Full verification is intentionally expensive
  and synchronous. Current HEAD being a later unarmed RESULT commit is not
  authority and must not invalidate a historically valid RESULT.
"""

from __future__ import annotations

import hashlib
import json
import math
import multiprocessing
import os
import subprocess
import sys
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping, Sequence

import numpy as np

from scripts.research.harness_synthetic_edge_calibration_v1_lib import (
    ERA_NAMES,
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
    _design_matrix,
    ae_metrics,
    candidate_features,
    compose_gates,
    era_mean_improvements,
    era_slices,
    expanding_era_predictions,
    linear_quantile,
    materiality_fraction_of_attainable,
    mechanical_conclusion,
    namespace_seed,
    pcg64_generator,
    power_verdict,
    predict,
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
WORKER_REL = "scripts/research/harness_synthetic_edge_calibration_v1_worker.py"
WORKER_PATH = WORKER_REL
# Live execution TCB. A future freeze/ARM must pin every path here. Historical
# ARM 0abc5fe listed only lib/runner/auth/production; worker.py is required
# for this HEAD and for any later ARM of this implementation.
EXECUTION_AUTHORITY_PATHS = (LIB_REL, RUNNER_REL, AUTH_REL, PRODUCTION_REL, WORKER_REL)
FROZEN_REVIEWED_LIB_SHA256 = (
    "12230dcad714e3a06d3f57de69b78fedcab088be950af3d06f959366f01d6c51"
)
FROZEN_WORKER_SHA256 = (
    "9aee03fdae012f9054c59adc4cea8072b88493521456fb6141ced926961c886e"
)
FROZEN_WORKER_SIZE = 3994
EXECUTION_WORKERS_ENV = "HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1_WORKERS"
VERIFY_WORKERS_ENV = "HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1_VERIFY_WORKERS"
BLAS_THREAD_LIMIT_KEYS = (
    "OPENBLAS_NUM_THREADS",
    "OMP_NUM_THREADS",
    "MKL_NUM_THREADS",
    "NUMEXPR_NUM_THREADS",
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
CANONICAL_DRIVER_FREEZE_PATH = (
    "docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1_PRODUCTION_DRIVER_FREEZE.json"
)
CANONICAL_WORLD_RECORDS_PATH = (
    "docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1_PRODUCTION_WORLD_RECORDS.json"
)
DURABLE_PARTIAL_KIND = "DURABLE_PARTIAL_WORLD_EVIDENCE"
DURABLE_PARTIAL_RECORD_KIND = "DURABLE_PARTIAL_WORLD_EVIDENCE_RECORD"
UNTRUSTED_CACHED_WORLD_RECORDS_KIND = "UNTRUSTED_CACHED_WORLD_RECORDS"
CHECKPOINT_CACHED = "CHECKPOINT_CACHED"
CHECKPOINT_STRUCTURALLY_VALID = "CHECKPOINT_STRUCTURALLY_VALID"
CHECKPOINT_SCIENTIFICALLY_VERIFIED = "CHECKPOINT_SCIENTIFICALLY_VERIFIED"
AUTHENTICATE_CACHED_RECORDS_PROOF_KIND = "CACHED_WORLD_RECORDS_FROZEN_EXECUTION_PROOF"
_AUTHENTICATE_CACHED_RECORDS_PROOF_KEYS = frozenset(
    {
        "schema_version",
        "kind",
        "mode",
        "verification_success",
        "trust_state",
        "execution_head",
        "execution_tree",
        "run_identity",
        "plan_sha256",
        "world_set_sha256",
        "record_digest_chain",
        "observed_world_count",
        "verification_authority",
    }
)
DURABLE_PARTIAL_REL = (
    "artifacts/research/harness_synthetic_edge_calibration_v1/"
    "durable_partial_world_evidence"
)
DURABLE_PARTIAL_IDENTITY_NAME = "STORE_IDENTITY.json"
# Module-private NON_PRODUCTION test hook. Production sessions refuse if set.
# Values: interrupt_after, crash_during_write, before_checkpoint.
_TEST_DURABILITY_HOOK: dict[str, Any] | None = None
TEST_CHECKPOINT_CRASH_ENV = "HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1_TEST_CHECKPOINT_CRASH"
TEST_INTERRUPT_AFTER_ENV = "HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1_TEST_INTERRUPT_AFTER"
WORKER_STDOUT_KIND_COMPLETE_RESULT = "COMPLETE_RESULT"
WORKER_STDOUT_KIND_PARTIAL = "PARTIAL_NOT_RESULT"
WORLD_RECORDS_KIND = "PRODUCTION_WORLD_RECORDS"
# Scientifically material literals a production RESULT core may never assert
# otherwise. Verified exactly during historical verification.
PRODUCTION_PROTECTED_CORE_LITERALS = {
    "production_calibration_executed": True,
    "production_monte_carlo_arm_authorized": True,
    "real_market_data_access_authorized": False,
    "b2_06_scientific_execution_authorized": False,
    "validation_2025_authorized": False,
    "oos_2026_authorized": False,
}
# Keys that must be absent from a production RESULT core entirely.
PRODUCTION_FORBIDDEN_CORE_KEYS = ("fixture", "not_a_production_result")
PRODUCTION_PROTECTED_AGGREGATE_LITERALS = {
    "real_market_data_access_authorized": False,
    "b2_06_scientific_execution_authorized": False,
    "validation_2025_authorized": False,
    "oos_2026_authorized": False,
}
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
HISTORICAL_RECOMPUTE_MODE = "historical-recompute"
AUTHENTICATE_CACHED_RECORDS_MODE = "authenticate-cached-records"
AUTHORITATIVE_HISTORICAL_VERIFICATION = "FULL_3200_RECOMPUTATION"
HISTORICAL_RECOMPUTE_PROOF_KIND = "HISTORICAL_RECOMPUTE_PROOF"
_HISTORICAL_RECOMPUTE_PROOF_KEYS = frozenset(
    {
        "schema_version",
        "kind",
        "mode",
        "verification",
        "verification_success",
        "execution_head",
        "execution_tree",
        "run_identity",
        "result_artifact_sha256",
        "result_artifact_size",
        "records_artifact_sha256",
        "records_artifact_size",
        "recomputed_world_records_sha256",
    }
)
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
FROZEN_WORKER = "9aee03fdae012f9054c59adc4cea8072b88493521456fb6141ced926961c886e"
FROZEN_WORKER_SIZE = 3994
FROZEN_PREREG_JSON = "78fcddf03ce84a0369a955d5b571c2423129d12b22e35f77eab26d6ac5eff708"
FROZEN_PREREG_MD = "a54c838d2b4903f039b4fd39d79198415ce095f5a9726fc51949cbb47153e5a3"
LIB_REL = "scripts/research/harness_synthetic_edge_calibration_v1_lib.py"
RUNNER_REL = "scripts/research/harness_synthetic_edge_calibration_v1.py"
AUTH_REL = "scripts/research/harness_synthetic_edge_calibration_v1_auth.py"
PRODUCTION_REL = "scripts/research/harness_synthetic_edge_calibration_v1_production.py"
WORKER_REL = "scripts/research/harness_synthetic_edge_calibration_v1_worker.py"
PREREG_JSON_REL = "docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1_PREREG.json"
PREREG_MD_REL = "docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1_PREREG.md"
AUTHORITY = (LIB_REL, RUNNER_REL, AUTH_REL, PRODUCTION_REL, WORKER_REL, PREREG_JSON_REL, PREREG_MD_REL)
ALLOWED_ROOT_PY = {"main.py"}
ALLOWED_ROOT_DIRS = {
    "analytics",
    "artifacts",
    "backfill",
    "common",
    "config",
    "data_ingestion",
    "deploy",
    "docs",
    "notifications",
    "runtime",
    "scripts",
    "storage",
    "symbols",
    "tests",
}

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
    if rel == WORKER_REL and digest != FROZEN_WORKER:
        refuse("HEAD worker is not the pinned execution-TCB implementation")
    if rel == WORKER_REL and len(blob) != FROZEN_WORKER_SIZE:
        refuse("HEAD worker size is not the pinned execution-TCB size")
    if rel == PREREG_JSON_REL and digest != FROZEN_PREREG_JSON:
        refuse("HEAD prereg JSON is not the frozen reviewed blob")
    if rel == PREREG_MD_REL and digest != FROZEN_PREREG_MD:
        refuse("HEAD prereg MD is not the frozen reviewed blob")
for child in root.iterdir():
    name = child.name
    if name.startswith(".") or name == "__pycache__":
        continue
    if child.is_file():
        if child.suffix in (".py", ".pyc", ".pyo", ".so") and name not in ALLOWED_ROOT_PY:
            refuse("repo-root module shadow is not allowed execution authority: " + name)
        continue
    if name in ALLOWED_ROOT_DIRS:
        continue
    if (child / "__init__.py").exists() or (child / "__init__.pyc").exists() or name.isidentifier():
        refuse("repo-root module shadow is not allowed execution authority: " + name)
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
    """Production Monte Carlo is not armed by a verified parent-authorizing ARM."""


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


def _parent_sha_of(repo_root: Path, commit: str) -> str | None:
    proc = subprocess.run(
        ["git", "-C", str(repo_root), "rev-parse", f"{commit}^"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if proc.returncode != 0:
        return None
    return proc.stdout.decode("ascii").strip().lower()


def _parent_sha(repo_root: Path) -> str | None:
    return _parent_sha_of(repo_root, "HEAD")


def _commit_exists(repo_root: Path, commit: str) -> bool:
    commit = str(commit or "").strip()
    if not commit:
        return False
    proc = subprocess.run(
        ["git", "-C", str(repo_root), "cat-file", "-t", commit],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if proc.returncode != 0:
        return False
    return proc.stdout.decode("ascii").strip() == "commit"


def _commit_changes_execution_authority(repo_root: Path, commit: str) -> bool:
    names = _git(repo_root, "diff-tree", "--no-commit-id", "--name-only", "-r", commit)
    forbidden = set(EXECUTION_AUTHORITY_PATHS) | {PREREG_JSON_REL, PREREG_MD_REL}
    return any(name in forbidden for name in names.decode("utf-8").splitlines())


def _commit_tree_sha(repo_root: Path, commit: str) -> str:
    return _git(repo_root, "rev-parse", f"{commit}^{{tree}}").decode("ascii").strip().lower()


def _authority_digests_at(repo_root: Path, commit: str) -> dict[str, str]:
    digests: dict[str, str] = {}
    mapping = {
        "lib": LIB_REL,
        "runner": RUNNER_REL,
        "auth": AUTH_REL,
        "production": PRODUCTION_REL,
        "worker": WORKER_REL,
        "prereg_json": PREREG_JSON_REL,
        "prereg_md": PREREG_MD_REL,
    }
    for key, rel in mapping.items():
        blob = _commit_blob(repo_root, commit, rel)
        if blob is None:
            if key == "worker":
                continue
            _refuse(f"execution authority missing from {commit}: {rel}")
        digests[key] = _sha256_bytes(blob)
    durability = _commit_blob(repo_root, commit, CANONICAL_DURABILITY_PATH)
    if durability is not None:
        digests["durability"] = _sha256_bytes(durability)
    freeze = _commit_blob(repo_root, commit, CANONICAL_DRIVER_FREEZE_PATH)
    if freeze is not None:
        digests["driver_freeze"] = _sha256_bytes(freeze)
    return digests


ARM_REQUIRED_LITERALS = {
    "authorized_run_count": 1,
    "scope": "production_synthetic_calibration_only",
    "production_only_scope": True,
    "authorization_consumed": False,
    "descendant_implementation_change_authorized": False,
    "real_market_data_access_authorized": False,
    "other_hypothesis_authorized": False,
    "B2_06_scientific_execution_authorized": False,
    "validation_2025_authorized": False,
    "oos_2026_authorized": False,
}
DRIVER_FREEZE_REQUIRED_LITERALS = {
    "production_monte_carlo_arm_authorized": False,
    "descendant_implementation_change_authorized": False,
    "authorization_consumed": False,
    "real_market_data_access_authorized": False,
    "other_hypothesis_authorized": False,
    "B2_06_scientific_execution_authorized": False,
    "validation_2025_authorized": False,
    "oos_2026_authorized": False,
    "freeze_docs_only": True,
}


def _is_ancestor(repo_root: Path, maybe_ancestor: str, commit: str) -> bool:
    proc = subprocess.run(
        ["git", "-C", str(repo_root), "merge-base", "--is-ancestor", maybe_ancestor, commit],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    return proc.returncode == 0


def _is_strict_ancestor(repo_root: Path, maybe_ancestor: str, commit: str) -> bool:
    ancestor = str(maybe_ancestor or "").strip().lower()
    commit = str(commit or "").strip().lower()
    if ancestor == commit:
        return False
    return _is_ancestor(repo_root, ancestor, commit)


def _load_commit_json(repo_root: Path, commit: str, git_path: str) -> dict[str, Any] | None:
    blob = _commit_blob(repo_root, commit, git_path)
    if blob is None:
        return None
    try:
        payload = json.loads(blob.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    return payload


def _arm_declared_contract_holds(payload: Mapping[str, Any]) -> bool:
    if not isinstance(payload, Mapping):
        return False
    for key, expected in ARM_REQUIRED_LITERALS.items():
        if payload.get(key) != expected:
            return False
    try:
        return payload.get("authorized_grid") == frozen_production_grid()
    except SyntheticExecutionNotAuthorized:
        return False


def _driver_freeze_binds_parent(
    repo_root: Path, payload: Mapping[str, Any], parent: str
) -> bool:
    freeze = _load_commit_json(repo_root, parent, CANONICAL_DRIVER_FREEZE_PATH)
    if freeze is None:
        return False
    for key, expected in DRIVER_FREEZE_REQUIRED_LITERALS.items():
        if freeze.get(key) != expected:
            return False
    freeze_status = freeze.get("freeze_status")
    if not isinstance(freeze_status, str) or not freeze_status.strip():
        return False
    reviewed_head = str(freeze.get("reviewed_implementation_head") or "").strip().lower()
    reviewed_tree = str(freeze.get("reviewed_implementation_tree") or "").strip().lower()
    if len(reviewed_head) != 40 or len(reviewed_tree) != 40:
        return False
    if any(ch not in "0123456789abcdef" for ch in reviewed_head + reviewed_tree):
        return False
    if reviewed_head == parent:
        return False
    if not _is_strict_ancestor(repo_root, reviewed_head, parent):
        return False
    if _commit_tree_sha(repo_root, reviewed_head) != reviewed_tree:
        return False
    arm_reviewed_head = str(payload.get("reviewed_implementation_head") or "").strip().lower()
    arm_reviewed_tree = str(payload.get("reviewed_implementation_tree") or "").strip().lower()
    if arm_reviewed_head != reviewed_head or arm_reviewed_tree != reviewed_tree:
        return False
    if arm_reviewed_head == parent:
        return False
    for rel in EXECUTION_AUTHORITY_PATHS:
        reviewed_bytes = _commit_blob(repo_root, reviewed_head, rel)
        parent_bytes = _commit_blob(repo_root, parent, rel)
        if reviewed_bytes is None and parent_bytes is None:
            continue
        if reviewed_bytes is None or parent_bytes is None or reviewed_bytes != parent_bytes:
            return False
    reviewed_production = _commit_blob(repo_root, reviewed_head, PRODUCTION_REL)
    parent_production = _commit_blob(repo_root, parent, PRODUCTION_REL)
    if reviewed_production is None or parent_production is None:
        return False
    freeze_production = str(freeze.get("reviewed_production_sha256") or "").strip().lower()
    if freeze_production != _sha256_bytes(reviewed_production):
        return False
    if freeze_production != _sha256_bytes(parent_production):
        return False
    listed = payload.get("execution_authority_sha256")
    if not isinstance(listed, dict):
        return False
    if str(listed.get("production") or "").strip().lower() != freeze_production:
        return False
    if str(freeze.get("frozen_lib_sha256") or "").strip().lower() != FROZEN_REVIEWED_LIB_SHA256:
        return False
    reviewed_lib = _commit_blob(repo_root, reviewed_head, LIB_REL)
    parent_lib = _commit_blob(repo_root, parent, LIB_REL)
    if reviewed_lib is None or parent_lib is None:
        return False
    if _sha256_bytes(reviewed_lib) != freeze["frozen_lib_sha256"]:
        return False
    if _sha256_bytes(parent_lib) != freeze["frozen_lib_sha256"]:
        return False
    for rel, freeze_key, bound_key in (
        (PREREG_JSON_REL, "prereg_json_sha256", "prereg_json"),
        (PREREG_MD_REL, "prereg_md_sha256", "prereg_md"),
    ):
        reviewed_blob = _commit_blob(repo_root, reviewed_head, rel)
        parent_blob = _commit_blob(repo_root, parent, rel)
        freeze_digest = str(freeze.get(freeze_key) or "").strip().lower()
        if reviewed_blob is None or parent_blob is None:
            return False
        if _sha256_bytes(reviewed_blob) != freeze_digest or _sha256_bytes(parent_blob) != freeze_digest:
            return False
        if str(listed.get(bound_key) or "").strip().lower() != freeze_digest:
            return False
    return True


def _reviewed_implementation_binds_parent(
    repo_root: Path, payload: Mapping[str, Any], parent: str
) -> bool:
    return _driver_freeze_binds_parent(repo_root, payload, parent)


def _arm_payload_authorizes_at_commit(
    repo_root: Path, commit: str, payload: Mapping[str, Any]
) -> bool:
    """ARM topology at an exact commit using git objects, not current HEAD."""
    if payload.get("production_monte_carlo_arm_authorized") is not True:
        return False
    if not _arm_declared_contract_holds(payload):
        return False
    parent = _parent_sha_of(repo_root, commit)
    if parent is None:
        return False
    authorized_commit = str(payload.get("authorized_execution_commit") or "").strip().lower()
    authorized_tree = str(payload.get("authorized_execution_tree") or "").strip().lower()
    if authorized_commit != parent:
        return False
    if authorized_tree != _commit_tree_sha(repo_root, parent):
        return False
    listed = payload.get("execution_authority_sha256")
    if not isinstance(listed, dict):
        return False
    try:
        actual = _authority_digests_at(repo_root, parent)
    except SyntheticExecutionNotAuthorized:
        return False
    required = ["lib", "runner", "auth", "production", "prereg_json", "prereg_md"]
    if actual.get("worker") is not None:
        required.append("worker")
        if "worker" not in listed:
            return False
    if any(key not in listed for key in required):
        return False
    for key, digest in listed.items():
        if actual.get(key) != str(digest).strip().lower():
            return False
    for rel in EXECUTION_AUTHORITY_PATHS:
        commit_bytes = _commit_blob(repo_root, commit, rel)
        parent_bytes = _commit_blob(repo_root, parent, rel)
        if commit_bytes is None and parent_bytes is None:
            continue
        if commit_bytes is None or parent_bytes is None or commit_bytes != parent_bytes:
            return False
    if not _reviewed_implementation_binds_parent(repo_root, payload, parent):
        return False
    return True


def _arm_payload_authorizes(repo_root: Path, payload: Mapping[str, Any]) -> bool:
    return _arm_payload_authorizes_at_commit(repo_root, _head_sha(repo_root), payload)


def inspect_production_arm_state(repo_root: Path | None = None) -> dict[str, Any]:
    """Inspect tracked ARM without granting authority. Fail closed if unverifiable."""
    root = repo_root or _repo_root()
    blob = _head_blob(root, CANONICAL_ARM_PATH)
    if blob is None:
        return {"present": False, "authorized": False}
    try:
        payload = json.loads(blob.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        _refuse("ARM artifact is present but cannot be verified")
    if not isinstance(payload, dict):
        _refuse("ARM artifact is present but cannot be verified")
    return {"present": True, "authorized": _arm_payload_authorizes(root, payload)}


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
    if not isinstance(payload, dict):
        return False
    return _arm_payload_authorizes(root, payload)


def _executing_file(rel: str) -> Path:
    names = {
        LIB_REL: "harness_synthetic_edge_calibration_v1_lib.py",
        RUNNER_REL: "harness_synthetic_edge_calibration_v1.py",
        AUTH_REL: "harness_synthetic_edge_calibration_v1_auth.py",
        PRODUCTION_REL: "harness_synthetic_edge_calibration_v1_production.py",
        WORKER_REL: "harness_synthetic_edge_calibration_v1_worker.py",
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
        if rel == WORKER_REL and digest != FROZEN_WORKER_SHA256:
            _refuse("HEAD worker is not the pinned execution-TCB implementation")
        if rel == WORKER_REL and len(head_bytes) != FROZEN_WORKER_SIZE:
            _refuse("HEAD worker size is not the pinned execution-TCB size")
        bound[rel] = digest
        if rel == WORKER_REL:
            bound["worker_sha256"] = digest
            bound["worker_size"] = str(len(head_bytes))
            bound["worker_path"] = WORKER_REL
            from scripts.research import harness_synthetic_edge_calibration_v1_worker as worker_mod

            imported = Path(getattr(worker_mod, "__file__", "") or "").resolve()
            if not imported.is_file() or imported.read_bytes() != head_bytes:
                _refuse("imported worker bytes differ from git HEAD")
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
            if rel == WORKER_REL:
                continue
            _refuse(f"execution authority missing from {commit}: {rel}")
        digest = _sha256_bytes(blob)
        if rel == LIB_REL and digest != FROZEN_REVIEWED_LIB_SHA256:
            _refuse("commit scientific lib is not the frozen reviewed implementation")
        bound[rel] = digest
        if rel == WORKER_REL:
            bound["worker_sha256"] = digest
            bound["worker_size"] = str(len(blob))
            bound["worker_path"] = WORKER_REL
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


def _authority_sha256_from_bound(bound: Mapping[str, str]) -> dict[str, str]:
    payload = {
        "lib": bound[LIB_REL],
        "runner": bound[RUNNER_REL],
        "auth": bound[AUTH_REL],
        "production": bound[PRODUCTION_REL],
    }
    if WORKER_REL in bound:
        payload["worker"] = bound[WORKER_REL]
    return payload


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
    if WORKER_REL in bound:
        payload["worker_sha256"] = bound[WORKER_REL]
        payload["worker_path"] = bound.get("worker_path", WORKER_REL)
        payload["worker_size"] = bound["worker_size"]
    return _sha256_bytes(canonical_json_bytes(payload))


def execution_tcb_manifest(*, repo_root: Path, execution_head: str) -> dict[str, Any]:
    """Tracked git-object execution TCB. Caller digests are not authority."""
    commit = str(execution_head or "").strip().lower()
    files: list[dict[str, Any]] = []
    for rel in EXECUTION_AUTHORITY_PATHS:
        blob = _commit_blob(repo_root, commit, rel)
        if blob is None:
            if rel == WORKER_REL:
                continue
            _refuse(f"execution TCB path missing from git object {commit}:{rel}")
        files.append(
            {
                "path": rel,
                "sha256": _sha256_bytes(blob),
                "size": len(blob),
            }
        )
    return {
        "kind": "HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1_EXECUTION_TCB",
        "schema_version": 1,
        "execution_head": commit,
        "files": files,
    }


def assert_execution_tcb_current(
    manifest: Mapping[str, Any],
    *args: Any,
    repo_root: Path | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Fail closed unless the manifest matches git objects at HEAD."""
    if args or kwargs:
        _refuse("caller arguments cannot authorize an execution TCB")
    if not isinstance(manifest, Mapping):
        _refuse("execution TCB manifest is malformed")
    root = repo_root or _repo_root()
    head = _head_sha(root)
    expected = execution_tcb_manifest(repo_root=root, execution_head=head)
    if manifest.get("kind") != expected["kind"]:
        _refuse("execution TCB manifest kind is not canonical")
    listed_head = str(manifest.get("execution_head") or "").strip().lower()
    if listed_head != head:
        _refuse("execution TCB manifest is stale")
    listed = manifest.get("files")
    if not isinstance(listed, list):
        _refuse("execution TCB manifest files are missing")
    expected_rows = {(item["path"], item["sha256"], int(item["size"])) for item in expected["files"]}
    listed_rows = set()
    for item in listed:
        if not isinstance(item, Mapping):
            _refuse("execution TCB manifest is malformed")
        listed_rows.add((item.get("path"), item.get("sha256"), item.get("size")))
    if listed_rows != expected_rows:
        _refuse("execution TCB manifest does not match git HEAD objects")
    if not any(path == WORKER_REL for path, _digest, _size in expected_rows):
        _refuse("execution TCB is missing worker.py")
    return expected


def planned_jobs_sha256(jobs: Sequence[tuple[str, int, int]]) -> str:
    planned = [(str(job[0]), int(job[1]), int(job[2])) for job in jobs]
    return _sha256_bytes(canonical_json_bytes({"jobs": [list(job) for job in planned]}))


def _fsync_directory(path: Path) -> None:
    fd = os.open(str(path), os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _durability_test_hook() -> dict[str, Any]:
    hook = dict(_TEST_DURABILITY_HOOK or {})
    crash = os.environ.get(TEST_CHECKPOINT_CRASH_ENV)
    if crash:
        hook["crash_during_write"] = True
    interrupt = os.environ.get(TEST_INTERRUPT_AFTER_ENV)
    if interrupt:
        hook["interrupt_after"] = int(str(interrupt).strip())
    return hook


def _refuse_production_durability_hooks() -> None:
    if _TEST_DURABILITY_HOOK:
        _refuse("durability test hooks cannot enter production")
    if os.environ.get(TEST_CHECKPOINT_CRASH_ENV):
        _refuse("durability test hooks cannot enter production")
    if os.environ.get(TEST_INTERRUPT_AFTER_ENV):
        _refuse("durability test hooks cannot enter production")


def _atomic_replace_bytes(final_path: Path, payload: bytes) -> None:
    """Crash-safe replace. A torn .tmp is never the durable object."""
    final_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = final_path.with_name(final_path.name + ".tmp")
    hook = _durability_test_hook()
    if hook.get("crash_during_write"):
        truncated = payload[: max(1, len(payload) // 2)]
        with open(tmp, "wb") as fh:
            fh.write(truncated)
            fh.flush()
            os.fsync(fh.fileno())
        raise RuntimeError("NON_PRODUCTION durability crash during checkpoint write")
    with open(tmp, "wb") as fh:
        fh.write(payload)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, final_path)
    _fsync_directory(final_path.parent)


def durable_partial_store_identity(
    *,
    bound: Mapping[str, str],
    planned: Sequence[tuple[str, int, int]],
    repo_root: Path,
) -> dict[str, Any]:
    return {
        "kind": DURABLE_PARTIAL_KIND,
        "schema_version": 1,
        "not_a_production_result": True,
        "not_canonical_world_records": True,
        "authorization_consumed": False,
        "calibration_complete": False,
        "production_calibration_executed": False,
        "execution_head": bound["head_sha"],
        "execution_tree": bound["tree_sha"],
        "run_identity": _run_identity_from_bound(bound),
        "plan_sha256": planned_jobs_sha256(planned),
        "tcb": execution_tcb_manifest(
            repo_root=repo_root, execution_head=str(bound["head_sha"])
        ),
        "worker_path": bound.get("worker_path", WORKER_REL if WORKER_REL in bound else None),
        "worker_sha256": bound.get("worker_sha256") or bound.get(WORKER_REL),
        "worker_size": bound.get("worker_size"),
    }


class DurablePartialWorldStore:
    """Append-safe per-world evidence. Never RESULT / WORLD_RECORDS / ARM consume."""

    def __init__(
        self,
        path: Path,
        *,
        bound: Mapping[str, str],
        planned: Sequence[tuple[str, int, int]],
        repo_root: Path,
        identity: Mapping[str, Any],
    ) -> None:
        self.path = Path(path)
        self.worlds_dir = self.path / "worlds"
        self.identity_path = self.path / DURABLE_PARTIAL_IDENTITY_NAME
        self.bound = dict(bound)
        self.planned = tuple((str(job[0]), int(job[1]), int(job[2])) for job in planned)
        self.planned_set = set(self.planned)
        self.repo_root = Path(repo_root)
        self.identity = dict(identity)

    @classmethod
    def open(
        cls,
        path: Path,
        *,
        bound: Mapping[str, str],
        planned: Sequence[tuple[str, int, int]],
        repo_root: Path,
    ) -> "DurablePartialWorldStore":
        store_path = Path(path)
        identity = durable_partial_store_identity(
            bound=bound, planned=planned, repo_root=repo_root
        )
        store = cls(
            store_path,
            bound=bound,
            planned=planned,
            repo_root=repo_root,
            identity=identity,
        )
        store._ensure_identity()
        return store

    def _ensure_identity(self) -> None:
        self.path.mkdir(parents=True, exist_ok=True)
        self.worlds_dir.mkdir(parents=True, exist_ok=True)
        if not self.identity_path.is_file():
            json_files = list(self.worlds_dir.glob("*.json"))
            if json_files:
                _refuse("durable partial worlds exist without a store identity")
            payload = canonical_json_bytes(_jsonable(self.identity))
            _atomic_replace_bytes(self.identity_path, payload)
            return
        existing = self._load_identity_file(self.identity_path)
        if existing.get("kind") != DURABLE_PARTIAL_KIND:
            _refuse("durable partial store identity kind is not canonical")
        if existing.get("not_a_production_result") is not True:
            _refuse("durable partial store must not claim a RESULT")
        if existing.get("not_canonical_world_records") is not True:
            _refuse("durable partial store must not claim WORLD_RECORDS")
        if existing.get("authorization_consumed") is True:
            _refuse("durable partial store must not consume one-shot authority")
        if existing.get("calibration_complete") is True:
            _refuse("durable partial store must not claim calibration complete")
        for key in (
            "execution_head",
            "execution_tree",
            "run_identity",
            "plan_sha256",
            "worker_sha256",
            "worker_size",
            "worker_path",
        ):
            if existing.get(key) != self.identity.get(key):
                _refuse("durable partial store does not match frozen execution identity")
        if not _canonical_equal(existing.get("tcb"), self.identity.get("tcb")):
            _refuse("durable partial store TCB does not match frozen execution identity")

    def _load_identity_file(self, path: Path) -> dict[str, Any]:
        raw = path.read_bytes()
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise SyntheticExecutionNotAuthorized(
                "SYNTHETIC_EXECUTION_NOT_AUTHORIZED: durable partial store identity is torn or malformed"
            ) from exc
        if not isinstance(payload, dict):
            _refuse("durable partial store identity is malformed")
        return payload

    def _world_path(self, world_id: str) -> Path:
        digest = _sha256_bytes(str(world_id).encode("utf-8"))
        return self.worlds_dir / f"{digest}.json"

    def load_structurally_valid_cached(self) -> dict[tuple[str, int, int], dict[str, Any]]:
        """UNTRUSTED cached records. Structural/digest checks only. Not scientific authority."""
        completed: dict[tuple[str, int, int], dict[str, Any]] = {}
        for path in sorted(self.worlds_dir.glob("*.json")):
            if path.name.endswith(".tmp"):
                continue
            rec_payload = self._load_world_file(path)
            job = (
                str(rec_payload["scenario_id"]),
                int(rec_payload["n_rows"]),
                int(rec_payload["world_index"]),
            )
            if job in completed:
                _refuse("duplicate persisted world identity")
            if job not in self.planned_set:
                _refuse("unexpected persisted world identity")
            completed[job] = rec_payload["record"]
        return completed

    def load_verified_completed(self) -> dict[tuple[str, int, int], dict[str, Any]]:
        """Compatibility alias. Returns STRUCTURALLY_VALID cached records, not science."""
        return self.load_structurally_valid_cached()

    def _load_world_file(self, path: Path) -> dict[str, Any]:
        raw = path.read_bytes()
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise SyntheticExecutionNotAuthorized(
                "SYNTHETIC_EXECUTION_NOT_AUTHORIZED: durable partial world record is torn or malformed"
            ) from exc
        if not isinstance(payload, dict):
            _refuse("durable partial world record is malformed")
        if payload.get("kind") != DURABLE_PARTIAL_RECORD_KIND:
            _refuse("durable partial world record kind is not canonical")
        if payload.get("completion_status") != "COMPLETE":
            _refuse("durable partial world record is not complete")
        for key in ("execution_head", "execution_tree", "run_identity", "plan_sha256"):
            if payload.get(key) != self.identity.get(key):
                _refuse("durable partial world record does not match frozen execution identity")
        record = payload.get("record")
        if not isinstance(record, Mapping):
            _refuse("durable partial world record body is missing")
        owned = _jsonable(dict(record))
        digest = _record_content_digest(owned)
        size = len(canonical_json_bytes(owned))
        if payload.get("record_sha256") != digest:
            _refuse("durable partial world record digest mismatch")
        if payload.get("record_size") != size:
            _refuse("durable partial world record size mismatch")
        job = (
            str(payload.get("scenario_id")),
            int(payload.get("n_rows", -1)),
            int(payload.get("world_index", -1)),
        )
        _record_job_identity(owned, *job)
        if str(payload.get("world_identity") or "") != str(owned.get("world_identity") or ""):
            _refuse("durable partial world identity mismatch")
        if int(payload.get("world_seed", -1)) != int(owned.get("world_seed", -1)):
            _refuse("durable partial world seed mismatch")
        payload["record"] = owned
        return payload

    def checkpoint_completed_world(
        self, rec: Mapping[str, Any], job: tuple[str, int, int]
    ) -> None:
        hook = _durability_test_hook()
        if hook.get("before_checkpoint"):
            raise RuntimeError("NON_PRODUCTION crash before durable checkpoint")
        job = (str(job[0]), int(job[1]), int(job[2]))
        if job not in self.planned_set:
            _refuse("unexpected world identity")
        owned = _jsonable(dict(rec))
        _record_job_identity(owned, *job)
        identity = str(owned["world_identity"])
        payload = {
            "kind": DURABLE_PARTIAL_RECORD_KIND,
            "schema_version": 1,
            "completion_status": "COMPLETE",
            "execution_head": self.identity["execution_head"],
            "execution_tree": self.identity["execution_tree"],
            "run_identity": self.identity["run_identity"],
            "plan_sha256": self.identity["plan_sha256"],
            "scenario_id": job[0],
            "n_rows": job[1],
            "world_index": job[2],
            "world_identity": identity,
            "world_seed": int(owned["world_seed"]),
            "record": owned,
            "record_sha256": _record_content_digest(owned),
            "record_size": len(canonical_json_bytes(owned)),
        }
        target = self._world_path(identity)
        if target.is_file():
            existing = self._load_world_file(target)
            if existing["record_sha256"] != payload["record_sha256"]:
                _refuse("duplicate persisted world identity")
            return
        _atomic_replace_bytes(target, canonical_json_bytes(_jsonable(payload)))


def canonical_run_identity(repo_root: Path | None = None) -> str:
    """Durable run identity from tracked execution-commit authority only."""
    root = repo_root or _repo_root()
    return _run_identity_from_bound(verify_executed_production_authority(root))


def _optional_head_sha256(repo_root: Path, git_path: str) -> str | None:
    blob = _head_blob(repo_root, git_path)
    if blob is None:
        return None
    return _sha256_bytes(blob)


def verify_historical_execution_authority(
    *, repo_root: Path, execution_commit: str
) -> dict[str, str]:
    """Prove execution_commit was correctly armed using git objects at that commit.

    Current HEAD being unarmed is irrelevant. This does not grant live ARM.
    """
    commit = str(execution_commit or "").strip().lower()
    if not _commit_exists(repo_root, commit):
        _refuse("execution commit does not exist in git")
    bound = _bound_from_commit_blobs(repo_root, commit)
    arm_blob = _commit_blob(repo_root, commit, CANONICAL_ARM_PATH)
    if arm_blob is None:
        _refuse("historical execution commit is not armed")
    try:
        payload = json.loads(arm_blob.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        _refuse("historical ARM artifact cannot be verified")
    if not isinstance(payload, dict):
        _refuse("historical ARM artifact cannot be verified")
    if not _arm_payload_authorizes_at_commit(repo_root, commit, payload):
        _refuse("historical execution commit ARM topology is not authorized")
    return bound


def _durable_reservation_from_bound(bound: Mapping[str, str]) -> dict[str, Any]:
    """Reservation identity from an exact bound. Does not consult current ARM."""
    return {
        "schema_version": "1.0",
        "durability_id": DURABILITY_ID,
        "unit_id": UNIT_ID,
        "canonical_path": CANONICAL_RESERVATION_PATH,
        "run_identity": _run_identity_from_bound(bound),
        "execution_head": bound["head_sha"],
        "execution_tree": bound["tree_sha"],
        "authority_sha256": _authority_sha256_from_bound(bound),
        "prereg_json_sha256": bound["prereg_json_sha256"],
        "prereg_md_sha256": bound["prereg_md_sha256"],
        "authorization_sha256": bound.get("authorization_sha256"),
        "lifecycle": "TRACKED_IDENTITY_UNARMED",
        "automatic_retry_authorized": False,
        "global_process_exclusion_claimed": False,
        "production_monte_carlo_arm_authorized": False,
    }


def _durable_claim_from_bound(bound: Mapping[str, str]) -> dict[str, Any]:
    """#115 claim identity from an exact bound. Does not consult current ARM."""
    reservation = _durable_reservation_from_bound(bound)
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


def durable_reservation_document(repo_root: Path | None = None) -> dict[str, Any]:
    """Reservation identity is a function of tracked commit authority only."""
    root = repo_root or _repo_root()
    return _durable_reservation_from_bound(verify_executed_production_authority(root))


def durable_claim_document(repo_root: Path | None = None) -> dict[str, Any]:
    """Claim identity is the same tracked run identity as the reservation."""
    root = repo_root or _repo_root()
    return _durable_claim_from_bound(verify_executed_production_authority(root))


def apply_worker_blas_thread_limits() -> None:
    """Force single-thread BLAS/OpenMP in this process and future workers."""
    for key in BLAS_THREAD_LIMIT_KEYS:
        os.environ[key] = "1"


def conservative_worker_count() -> int:
    """Operator hint. Never an implicit production default; do not use cpu_count() raw."""
    detected = os.cpu_count()
    if detected is None or int(detected) < 1:
        return 1
    return max(1, min(int(detected) // 2, 16))


def resolve_execution_workers(workers: object | None = None) -> int:
    """Explicit worker count. Default is 1. Env is read only when workers is None."""
    if workers is None:
        raw = os.environ.get(EXECUTION_WORKERS_ENV, "1")
        try:
            workers = int(str(raw).strip() or "1")
        except (TypeError, ValueError):
            _refuse("workers must be a positive int")
    if type(workers) is not int or workers < 1:
        _refuse("workers must be a positive int")
    return workers


def resolve_verification_workers(workers: object | None = None) -> int:
    """Operational verifier parallelism. Not scientific authority.

    Worker count must not change world identities, seeds, records, digests,
    or mechanical conclusions. Default is 1. If VERIFY_WORKERS is unset,
    EXECUTION_WORKERS is reused so mint/claim verification can share the same
    operational pool size as compute. An explicit `workers` argument wins.
    """
    if workers is None:
        raw = os.environ.get(VERIFY_WORKERS_ENV)
        if raw is None or str(raw).strip() == "":
            raw = os.environ.get(EXECUTION_WORKERS_ENV, "1")
        try:
            workers = int(str(raw).strip() or "1")
        except (TypeError, ValueError):
            _refuse("verification workers must be a positive int")
    if type(workers) is not int or workers < 1:
        _refuse("verification workers must be a positive int")
    return workers


def fit_lstsq_lstsq_rank(x: np.ndarray, y: np.ndarray) -> np.ndarray:
    """Single-factorization OLS rank decision.

    Frozen `fit_lstsq` calls `matrix_rank` then `lstsq`. numpy.linalg.lstsq
    with rcond=None already returns rank under the same default cutoff.
    Rank-deficient designs still raise IncompleteWorld with the frozen
    message and do not return coefficients. Success-path coefficients are
    the lstsq result, matching the frozen second factorization.
    """
    x = np.asarray(x, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    if x.ndim != 2 or y.ndim != 1 or x.shape[0] != y.shape[0]:
        raise IncompleteWorld("design shape invalid")
    coef, _residuals, rank, _sv = np.linalg.lstsq(x, y, rcond=None)
    if int(rank) < x.shape[1]:
        raise IncompleteWorld("design is not full rank")
    coef = np.asarray(coef, dtype=np.float64)
    if coef.shape[0] != x.shape[1] or not np.all(np.isfinite(coef)):
        raise IncompleteWorld("non-finite coefficients")
    return coef


def _expanding_era_predictions_hot(
    y: np.ndarray,
    x1: np.ndarray,
    x2: np.ndarray,
    feature: np.ndarray | None,
    n_rows: int,
    *,
    base_pred: np.ndarray | None = None,
) -> dict[str, np.ndarray]:
    """Same era boundaries as frozen expanding_era_predictions; optional BASE reuse."""
    slices = era_slices(n_rows)
    compute_base = base_pred is None
    if compute_base:
        base_out = np.full(n_rows, np.nan, dtype=np.float64)
    else:
        base_out = np.asarray(base_pred, dtype=np.float64)
        if base_out.shape != (n_rows,):
            raise IncompleteWorld("design shape invalid")
    cand_pred = np.full(n_rows, np.nan, dtype=np.float64)
    train_end_by_score_era: dict[str, int] = {}
    for era_i, era_name in enumerate(ERA_NAMES):
        if era_i == 0:
            continue
        train = slice(0, slices[era_name].start)
        score = slices[era_name]
        train_end_by_score_era[era_name] = train.stop
        if train.stop > score.start:
            raise IncompleteWorld("lookahead: future era entered earlier fit")
        y_train = y[train]
        if compute_base:
            x_base_train = _design_matrix(x1[train], x2[train])
            x_base_score = _design_matrix(x1[score], x2[score])
            base_coef = fit_lstsq_lstsq_rank(x_base_train, y_train)
            base_out[score] = predict(x_base_score, base_coef)
        if feature is not None:
            x_cand_train = _design_matrix(x1[train], x2[train], feature[train])
            x_cand_score = _design_matrix(x1[score], x2[score], feature[score])
            cand_coef = fit_lstsq_lstsq_rank(x_cand_train, y_train)
            cand_pred[score] = predict(x_cand_score, cand_coef)
    return {
        "BASE_PRED": base_out,
        "CAND_PRED": cand_pred,
        "train_end_by_score_era": train_end_by_score_era,  # type: ignore[dict-item]
    }


def placebo_q95_base_cached(
    *,
    world: Mapping[str, np.ndarray],
    feature: np.ndarray,
    n_rows: int,
    replicates: int,
    rng: np.random.Generator,
) -> dict[str, Any]:
    """Placebo_q95 with BASE expanding-era predictions computed once.

    Permutation RNG consumption matches frozen sequential placebo_q95:
    each replicate permutes the candidate inside every era, then refits
    the candidate model. BASE (Y ~ 1+X1+X2) does not depend on the
    permutation and is reused. If BASE is IncompleteWorld, permutation
    loops still run and every replicate is treated as invalid.
    """
    y = np.asarray(world["Y"], dtype=np.float64)
    x1 = np.asarray(world["X1"], dtype=np.float64)
    x2 = np.asarray(world["X2"], dtype=np.float64)
    slices = era_slices(n_rows)
    mask = scored_mask(n_rows)
    stats: list[float] = []
    invalid = False
    base_pred: np.ndarray | None = None
    base_failed = False
    try:
        base_pred = _expanding_era_predictions_hot(y, x1, x2, None, n_rows)["BASE_PRED"]
    except IncompleteWorld:
        base_failed = True
    for _ in range(replicates):
        permuted = np.asarray(feature, dtype=np.float64).copy()
        for slc in slices.values():
            idx = np.arange(slc.start, slc.stop)
            permuted[idx] = permuted[idx][rng.permutation(idx.size)]
        if base_failed:
            invalid = True
            continue
        try:
            preds = _expanding_era_predictions_hot(
                y, x1, x2, permuted, n_rows, base_pred=base_pred
            )
            metrics = ae_metrics(y, preds["BASE_PRED"], preds["CAND_PRED"], mask)
            value = metrics["MEAN_AE_IMPROVEMENT"]
        except IncompleteWorld:
            invalid = True
            continue
        if not np.isfinite(value):
            invalid = True
            continue
        stats.append(float(value))
    if invalid or len(stats) != replicates:
        return {
            "placebo_q95": float("nan"),
            "placebo_invalid": True,
            "world_invalid": True,
            "stays_in_denominator": True,
        }
    return {
        "placebo_q95": linear_quantile(stats, 0.95),
        "placebo_invalid": False,
        "world_invalid": False,
        "stays_in_denominator": True,
    }


def placebo_q95(
    *,
    world: Mapping[str, np.ndarray],
    feature: np.ndarray,
    n_rows: int,
    replicates: int,
    rng: np.random.Generator,
) -> dict[str, Any]:
    """Production placebo entry. Tests may monkeypatch this name."""
    return placebo_q95_base_cached(
        world=world,
        feature=feature,
        n_rows=n_rows,
        replicates=replicates,
        rng=rng,
    )


def assemble_canonical_world_records(
    *,
    planned_jobs: Sequence[tuple[str, int, int]],
    completed_records: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Reorder unordered worker records into frozen planned job order. Fail-closed."""
    if isinstance(completed_records, (str, bytes)) or not isinstance(completed_records, Sequence):
        _refuse("malformed worker record set")
    planned = tuple((str(job[0]), int(job[1]), int(job[2])) for job in planned_jobs)
    planned_set = set(planned)
    if len(planned) != len(planned_set):
        _refuse("planned jobs contain duplicate world identities")
    by_job: dict[tuple[str, int, int], Mapping[str, Any]] = {}
    for rec in completed_records:
        if not isinstance(rec, Mapping):
            _refuse("malformed worker record")
        try:
            job = (
                str(rec["scenario_id"]),
                int(rec["n_rows"]),
                int(rec["world_index"]),
            )
        except Exception:
            _refuse("malformed worker record")
        if job not in planned_set:
            _refuse("unexpected world identity")
        if job in by_job:
            _refuse("duplicate world identity")
        _record_job_identity(rec, *job)
        by_job[job] = rec
    ordered: list[dict[str, Any]] = []
    for job in planned:
        if job not in by_job:
            _refuse("missing planned world")
        owned = _jsonable(dict(by_job.pop(job)))
        ordered.append(owned)
    if by_job:
        _refuse("unexpected extra world identities")
    return ordered


def evaluate_planned_jobs_fail_closed(
    jobs: Sequence[tuple[str, int, int]],
    *,
    workers: int = 1,
    durable_partial: DurablePartialWorldStore | None = None,
    **kwargs: Any,
) -> list[dict[str, Any]]:
    """Evaluate planned jobs; reorder to planned order before returning.

    Does not read ARM, mint RESULT, or write WORLD_RECORDS. Worker scheduling
    cannot seed science. Fail-closed on crash/malformed/duplicate/missing/
    unexpected identities. Caller digests cannot pin the worker.

    Durable checkpoints are UNTRUSTED cached compute. Resume may reuse
    STRUCTURALLY_VALID records to avoid immediate recomputation. They are not
    scientific authority and cannot enter WORLD_RECORDS/RESULT until isolated
    frozen-git authentication succeeds.
    """
    if kwargs:
        _refuse("caller arguments cannot authorize worker/execution identity")
    planned = tuple((str(job[0]), int(job[1]), int(job[2])) for job in jobs)
    workers_n = resolve_execution_workers(workers)
    apply_worker_blas_thread_limits()
    completed_by_job: dict[tuple[str, int, int], Mapping[str, Any]] = {}
    if durable_partial is not None:
        completed_by_job = dict(durable_partial.load_structurally_valid_cached())
    _interrupt_after_checkpoint_if_needed(len(completed_by_job))
    missing = [job for job in planned if job not in completed_by_job]
    if missing:
        if workers_n == 1:
            for job in missing:
                rec = _evaluate_planned_world_body(*job)
                _accept_completed_world(rec, job, durable_partial, completed_by_job)
        else:
            for rec in _evaluate_jobs_multiprocess(missing, workers_n):
                job = _job_from_record(rec)
                _accept_completed_world(rec, job, durable_partial, completed_by_job)
    ordered = [completed_by_job[job] for job in planned]
    return assemble_canonical_world_records(
        planned_jobs=planned, completed_records=ordered
    )


def _accept_completed_world(
    rec: Mapping[str, Any],
    job: tuple[str, int, int],
    durable_partial: DurablePartialWorldStore | None,
    completed_by_job: dict[tuple[str, int, int], Mapping[str, Any]],
) -> None:
    job = (str(job[0]), int(job[1]), int(job[2]))
    if durable_partial is not None:
        durable_partial.checkpoint_completed_world(rec, job)
    completed_by_job[job] = rec
    _interrupt_after_checkpoint_if_needed(len(completed_by_job))


def _interrupt_after_checkpoint_if_needed(completed_count: int) -> None:
    hook = _durability_test_hook()
    after = hook.get("interrupt_after")
    if after is None:
        return
    if completed_count >= int(after):
        raise RuntimeError("NON_PRODUCTION durability interrupt after checkpoint")


def _untrusted_cached_records_payload(
    *,
    bound: Mapping[str, str],
    planned: Sequence[tuple[str, int, int]],
    records: Sequence[Mapping[str, Any]],
    production: bool,
) -> dict[str, Any]:
    planned_jobs = tuple((str(job[0]), int(job[1]), int(job[2])) for job in planned)
    ordered = assemble_canonical_world_records(
        planned_jobs=planned_jobs, completed_records=records
    )
    return {
        "kind": UNTRUSTED_CACHED_WORLD_RECORDS_KIND,
        "schema_version": 1,
        "not_scientific_authority": True,
        "not_a_production_result": production is not True,
        "not_canonical_world_records": True,
        "trust_state": CHECKPOINT_STRUCTURALLY_VALID,
        "production": bool(production),
        "execution_head": bound["head_sha"],
        "execution_tree": bound["tree_sha"],
        "run_identity": _run_identity_from_bound(bound),
        "plan_sha256": planned_jobs_sha256(planned_jobs),
        "jobs": [list(job) for job in planned_jobs],
        "records": _jsonable(list(ordered)),
    }


def authenticate_cached_world_records_from_frozen_execution(
    *,
    planned: Sequence[tuple[str, int, int]],
    records: Sequence[Mapping[str, Any]],
    repo_root: Path | None = None,
    production: bool = False,
    workers: object | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Authenticate untrusted cached records against isolated frozen git bytes.

    The parent does not recompute science and has no in-process fallback.
    Checkpoint self-hashes are not scientific authority. `workers` is
    operational parallelism only.
    """
    if kwargs:
        _refuse("caller arguments cannot authorize cached-record authentication")
    root = Path(repo_root) if repo_root is not None else _repo_root()
    bound = verify_executed_production_authority(root)
    planned_jobs = tuple((str(job[0]), int(job[1]), int(job[2])) for job in planned)
    if production:
        if planned_jobs != planned_production_jobs():
            _refuse("production authentication plan is not the frozen 3200-world plan")
    else:
        _fixture_jobs_forbidden_as_production(planned_jobs)
    workers_n = resolve_verification_workers(workers)
    payload = _untrusted_cached_records_payload(
        bound=bound,
        planned=planned_jobs,
        records=records,
        production=production,
    )
    try:
        completed = _spawn_isolated_child(
            AUTHENTICATE_CACHED_RECORDS_MODE,
            repo_root=root,
            text=False,
            stdin=canonical_json_bytes(_jsonable(payload)),
            extra_env={VERIFY_WORKERS_ENV: str(workers_n)},
        )
    except OSError as exc:
        _refuse(f"isolated cached-record authentication child could not spawn: {exc}")
    if int(completed.returncode) != 0:
        detail = _isolated_child_stderr_text(completed).strip()
        first = detail.splitlines()[0] if detail else (
            f"isolated cached-record authentication child failed (exit {int(completed.returncode)})"
        )
        if first.startswith("SYNTHETIC_EXECUTION_NOT_AUTHORIZED"):
            raise SyntheticExecutionNotAuthorized(first)
        _refuse(f"cached world records do not match frozen execution: {first}")
    proof = _parse_authenticate_cached_records_proof(completed.stdout or b"")
    expected_world = _sha256_bytes(
        canonical_json_bytes({"worlds": _jsonable(list(payload["records"]))})
    )
    expected_chain = list(_ordered_record_digest_chain(payload["records"]))
    if proof.get("execution_head") != bound["head_sha"]:
        _refuse("cached-record authentication proof execution_head does not match git HEAD")
    if proof.get("execution_tree") != bound["tree_sha"]:
        _refuse("cached-record authentication proof execution_tree does not match git HEAD")
    if proof.get("run_identity") != _run_identity_from_bound(bound):
        _refuse("cached-record authentication proof run_identity does not match git HEAD")
    if proof.get("plan_sha256") != planned_jobs_sha256(planned_jobs):
        _refuse("cached-record authentication proof plan does not match the submitted jobs")
    if proof.get("world_set_sha256") != expected_world:
        _refuse("cached world records do not match frozen execution")
    if not _canonical_equal(proof.get("record_digest_chain"), expected_chain):
        _refuse("cached world records do not match frozen execution")
    if type(proof.get("observed_world_count")) is not int:
        _refuse("cached-record authentication observed_world_count is not an int")
    if proof.get("observed_world_count") != len(payload["records"]):
        _refuse("cached-record authentication observed_world_count does not match submitted records")
    if proof.get("observed_world_count") != len(planned_jobs):
        _refuse("cached-record authentication observed_world_count does not match planned jobs")
    if proof.get("trust_state") != CHECKPOINT_SCIENTIFICALLY_VERIFIED:
        _refuse("cached-record authentication did not derive SCIENTIFICALLY_VERIFIED")
    return proof


def _parse_authenticate_cached_records_proof(raw: bytes) -> dict[str, Any]:
    if not raw:
        _refuse("isolated cached-record authentication child produced no proof")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise SyntheticExecutionNotAuthorized(
            "SYNTHETIC_EXECUTION_NOT_AUTHORIZED: isolated cached-record authentication proof is not UTF-8"
        ) from exc
    decoder = json.JSONDecoder()
    try:
        payload, end = decoder.raw_decode(text)
    except json.JSONDecodeError as exc:
        raise SyntheticExecutionNotAuthorized(
            "SYNTHETIC_EXECUTION_NOT_AUTHORIZED: isolated cached-record authentication proof is not JSON"
        ) from exc
    if text[end:].strip():
        _refuse("isolated cached-record authentication child produced duplicate or trailing output")
    if not isinstance(payload, dict):
        _refuse("isolated cached-record authentication proof is not an object")
    if frozenset(payload) != _AUTHENTICATE_CACHED_RECORDS_PROOF_KEYS:
        _refuse("isolated cached-record authentication proof keys are not canonical")
    if payload.get("schema_version") != "1.0":
        _refuse("isolated cached-record authentication proof schema is not canonical")
    if payload.get("kind") != AUTHENTICATE_CACHED_RECORDS_PROOF_KIND:
        _refuse("isolated cached-record authentication proof kind is not canonical")
    if payload.get("mode") != AUTHENTICATE_CACHED_RECORDS_MODE:
        _refuse("isolated cached-record authentication proof mode is not canonical")
    if payload.get("verification_success") is not True:
        _refuse("isolated cached-record authentication proof did not attest success")
    if payload.get("verification_authority") != "ISOLATED_FROZEN_GIT_EXECUTION":
        _refuse("cached-record authentication authority is not isolated frozen git bytes")
    if type(payload.get("observed_world_count")) is not int:
        _refuse("isolated cached-record authentication proof observed_world_count is not an int")
    return payload


def authenticate_cached_records_worker_main() -> dict[str, Any]:
    """Isolated child: recompute planned jobs from frozen git bytes and compare."""
    root = _repo_root()
    bound = verify_executed_production_authority(root)
    raw = sys.stdin.buffer.read()
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SyntheticExecutionNotAuthorized(
            "SYNTHETIC_EXECUTION_NOT_AUTHORIZED: untrusted cached records payload is malformed"
        ) from exc
    if not isinstance(payload, dict):
        _refuse("untrusted cached records payload is malformed")
    if payload.get("kind") != UNTRUSTED_CACHED_WORLD_RECORDS_KIND:
        _refuse("cached records payload kind is not untrusted")
    if payload.get("not_scientific_authority") is not True:
        _refuse("cached records must be marked untrusted")
    if payload.get("trust_state") == CHECKPOINT_SCIENTIFICALLY_VERIFIED:
        _refuse("checkpoint must not self-attest scientific verification")
    jobs_raw = payload.get("jobs")
    records = payload.get("records")
    if not isinstance(jobs_raw, list) or not isinstance(records, list):
        _refuse("untrusted cached records payload is missing jobs or records")
    jobs = tuple((str(job[0]), int(job[1]), int(job[2])) for job in jobs_raw)
    production = payload.get("production") is True
    if production:
        if jobs != planned_production_jobs():
            _refuse("production authentication plan is not the frozen 3200-world plan")
    else:
        _fixture_jobs_forbidden_as_production(jobs)
    if str(payload.get("execution_head") or "") != bound["head_sha"]:
        _refuse("cached records execution_head does not match isolated git HEAD")
    if str(payload.get("execution_tree") or "") != bound["tree_sha"]:
        _refuse("cached records execution_tree does not match isolated git HEAD")
    if payload.get("run_identity") != _run_identity_from_bound(bound):
        _refuse("cached records run_identity does not match isolated git HEAD")
    if payload.get("plan_sha256") != planned_jobs_sha256(jobs):
        _refuse("cached records plan_sha256 does not match isolated planned jobs")
    cached = assemble_canonical_world_records(planned_jobs=jobs, completed_records=records)
    recomputed = _evaluate_jobs_for_verification(
        jobs, resolve_verification_workers(None)
    )
    cached_bytes = canonical_json_bytes({"worlds": cached})
    recomputed_bytes = canonical_json_bytes({"worlds": recomputed})
    if cached_bytes != recomputed_bytes:
        _refuse("cached world records do not match frozen execution")
    return {
        "schema_version": "1.0",
        "kind": AUTHENTICATE_CACHED_RECORDS_PROOF_KIND,
        "mode": AUTHENTICATE_CACHED_RECORDS_MODE,
        "verification_success": True,
        "trust_state": CHECKPOINT_SCIENTIFICALLY_VERIFIED,
        "execution_head": bound["head_sha"],
        "execution_tree": bound["tree_sha"],
        "run_identity": _run_identity_from_bound(bound),
        "plan_sha256": planned_jobs_sha256(jobs),
        "world_set_sha256": _sha256_bytes(recomputed_bytes),
        "record_digest_chain": list(_ordered_record_digest_chain(recomputed)),
        "observed_world_count": len(recomputed),
        "verification_authority": "ISOLATED_FROZEN_GIT_EXECUTION",
    }


def _job_from_record(rec: Mapping[str, Any]) -> tuple[str, int, int]:
    return (str(rec["scenario_id"]), int(rec["n_rows"]), int(rec["world_index"]))


def _spawn_worker_pin(repo_root: Path) -> tuple[str, str]:
    """Pin spawn workers to git HEAD worker bytes. Caller digests are ignored."""
    blob = _head_blob(repo_root, WORKER_REL)
    if blob is None:
        _refuse("worker.py missing from git HEAD execution authority")
    digest = _sha256_bytes(blob)
    if digest != FROZEN_WORKER_SHA256:
        _refuse("git HEAD worker is not the pinned execution-TCB implementation")
    if len(blob) != FROZEN_WORKER_SIZE:
        _refuse("git HEAD worker size is not the pinned execution-TCB size")
    executing = _executing_file(WORKER_REL)
    if executing.read_bytes() != blob:
        _refuse("executed worker bytes differ from git HEAD")
    worktree = repo_root / WORKER_REL
    if worktree.is_symlink() or not worktree.is_file() or worktree.read_bytes() != blob:
        _refuse("worktree worker bytes differ from git HEAD")
    return digest, str(executing.resolve())


def _evaluate_jobs_multiprocess(
    planned: Sequence[tuple[str, int, int]],
    workers: int,
) -> list[Mapping[str, Any]]:
    """World-parallel spawn over the pinned worker module.

    Spawn imports the mapped function's module before Pool initializer
    runs. Mapping a production.py helper would re-import this file in
    every child (pytest deadlock). Mapping worker.evaluate_job_payload
    keeps the child TCB as worker.py plus the frozen package it imports.

    Spawn children inherit cwd and PYTHONPATH. The frozen worker repo
    root is forced first so children cannot import a different live
    checkout of the same module name. Worker count is operational.
    """
    apply_worker_blas_thread_limits()
    payloads = [(str(job[0]), int(job[1]), int(job[2])) for job in planned]
    root = _repo_root()
    digest, worker_path = _spawn_worker_pin(root)
    from scripts.research.harness_synthetic_edge_calibration_v1_worker import (
        evaluate_job_payload,
        multiprocessing_worker_init,
    )

    frozen_root = str(Path(worker_path).resolve().parents[2])
    old_cwd = os.getcwd()
    old_pp = os.environ.get("PYTHONPATH")
    old_sys_path = list(sys.path)
    completed: list[Mapping[str, Any]] = []
    try:
        # spawn copies the parent's sys.path into children before Pool
        # initializer runs. Frozen root must be first in the parent so
        # children import the pinned worker bytes, not a live checkout.
        while frozen_root in sys.path:
            sys.path.remove(frozen_root)
        sys.path.insert(0, frozen_root)
        os.chdir(frozen_root)
        os.environ["PYTHONPATH"] = (
            frozen_root if not old_pp else frozen_root + os.pathsep + old_pp
        )
        ctx = multiprocessing.get_context("spawn")
        with ctx.Pool(
            processes=int(workers),
            initializer=multiprocessing_worker_init,
            initargs=(digest, worker_path),
        ) as pool:
            for rec in pool.imap_unordered(
                evaluate_job_payload, payloads, chunksize=1
            ):
                completed.append(rec)
    except SyntheticExecutionNotAuthorized:
        raise
    except Exception as exc:
        _refuse(f"worker execution failed closed: {type(exc).__name__}: {exc}")
    finally:
        sys.path[:] = old_sys_path
        os.chdir(old_cwd)
        if old_pp is None:
            os.environ.pop("PYTHONPATH", None)
        else:
            os.environ["PYTHONPATH"] = old_pp
    if not isinstance(completed, list):
        _refuse("malformed worker record set")
    if len(completed) != len(payloads):
        _refuse("worker execution failed closed: incomplete world set")
    return completed


def _evaluate_jobs_for_verification(
    jobs: Sequence[tuple[str, int, int]],
    workers: object | None = None,
) -> list[dict[str, Any]]:
    """Recompute planned jobs with optional world-parallel spawn workers.

    Worker count is operational. Results are canonical-reordered before
    return. Used by isolated authentication and historical recomputation.
    """
    planned = tuple((str(job[0]), int(job[1]), int(job[2])) for job in jobs)
    workers_n = resolve_verification_workers(workers)
    apply_worker_blas_thread_limits()
    if workers_n == 1:
        completed = [
            _jsonable(_evaluate_planned_world_body(*job)) for job in planned
        ]
    else:
        completed = [
            _jsonable(rec) for rec in _evaluate_jobs_multiprocess(planned, workers_n)
        ]
    return assemble_canonical_world_records(
        planned_jobs=planned, completed_records=completed
    )


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


def _evaluate_planned_world_body(scenario_id: str, n_rows: int, world_index: int) -> dict[str, Any]:
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
    return _evaluate_planned_world_body(scenario_id, n_rows, world_index)


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


def _record_content_digest(rec: Mapping[str, Any]) -> str:
    return _sha256_bytes(canonical_json_bytes(_jsonable(dict(rec))))


def _immutable_record(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({str(key): _immutable_record(val) for key, val in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_immutable_record(item) for item in value)
    return value


def _mac_record_digest_chain(secret: bytes, digests: Sequence[str]) -> str:
    mac = hashlib.sha256(secret)
    for digest in digests:
        mac.update(b"\x00")
        mac.update(str(digest).encode("ascii"))
    return mac.hexdigest()


def _ordered_record_digest_chain(records: Sequence[Mapping[str, Any]]) -> tuple[str, ...]:
    return tuple(_record_content_digest(rec) for rec in records)


def _bind_result_core_from_bound(
    records,
    *,
    bound: Mapping[str, str],
    fixture: bool = False,
    armed: bool,
):
    """Reconstruct a RESULT core from an exact execution bound.

    `armed` must be the ARM state at the execution commit, not current HEAD.
    """
    reservation = _durable_reservation_from_bound(bound)
    if fixture:
        jsonable_records = [_jsonable(dict(rec)) for rec in records]
        digest_chain = list(_ordered_record_digest_chain(jsonable_records))
        return {
            "schema_version": "1.0",
            "fixture": True,
            "not_a_production_result": True,
            "unit_id": UNIT_ID,
            "durability_id": DURABILITY_ID,
            "execution_head": bound["head_sha"],
            "execution_tree": bound["tree_sha"],
            "run_identity": _run_identity_from_bound(bound),
            "reservation_sha256": _sha256_bytes(canonical_json_bytes(reservation)),
            "world_set_sha256": _sha256_bytes(
                canonical_json_bytes({"worlds": jsonable_records})
            ),
            "record_digest_chain": digest_chain,
            "records": jsonable_records,
            "planned_world_count": len(records),
            "observed_world_count": len(records),
            "mechanical_conclusion": "FIXTURE_COMPLETE_NOT_PRODUCTION",
            "real_market_data_access_authorized": False,
            "b2_06_scientific_execution_authorized": False,
            "validation_2025_authorized": False,
            "oos_2026_authorized": False,
            "production_monte_carlo_arm_authorized": armed,
            "production_calibration_executed": False,
        }
    records = _require_canonical_production_records(records)
    digest_chain = list(_ordered_record_digest_chain(records))
    aggregates = aggregate_planned_worlds(records)
    claim = _durable_claim_from_bound(bound)
    artifact = _production_world_records_from_bound(records, bound=bound)
    artifact_bytes = canonical_json_bytes(_jsonable(artifact))
    artifact_digest = _sha256_bytes(artifact_bytes)
    artifact_size = len(artifact_bytes)
    return {
        "schema_version": "1.0",
        "unit_id": UNIT_ID,
        "durability_id": DURABILITY_ID,
        "execution_head": bound["head_sha"],
        "execution_tree": bound["tree_sha"],
        "authority_paths": list(EXECUTION_AUTHORITY_PATHS),
        "authority_sha256": _authority_sha256_from_bound(bound),
        "prereg_json_sha256": bound["prereg_json_sha256"],
        "prereg_md_sha256": bound["prereg_md_sha256"],
        "frozen_lib_sha256": bound[LIB_REL],
        "authorization_sha256": bound.get("authorization_sha256"),
        "reservation_sha256": _sha256_bytes(canonical_json_bytes(reservation)),
        "claim_sha256": _sha256_bytes(canonical_json_bytes(claim)),
        "run_identity": _run_identity_from_bound(bound),
        "world_set_sha256": world_set_sha256(records),
        "record_digest_chain": digest_chain,
        "records_artifact_path": CANONICAL_WORLD_RECORDS_PATH,
        "records_artifact_sha256": artifact_digest,
        "records_artifact_size": artifact_size,
        "record_count": PRODUCTION_PLANNED_TOTAL_WORLDS,
        "planned_world_count": aggregates["planned_world_count"],
        "observed_world_count": aggregates["observed_world_count"],
        "aggregates": _jsonable(aggregates),
        "mechanical_conclusion": aggregates["mechanical_conclusion"],
        "real_market_data_access_authorized": False,
        "b2_06_scientific_execution_authorized": False,
        "validation_2025_authorized": False,
        "oos_2026_authorized": False,
        "production_monte_carlo_arm_authorized": armed,
        # A complete production core describes an executed calibration. The
        # historical verifier checks this literal, so mint and verify agree.
        "production_calibration_executed": True,
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


def _bind_result_core(*, records, repo_root, fixture: bool = False):
    """LIVE core builder from current HEAD. Public mint requires a session capability."""
    bound = verify_executed_production_authority(repo_root)
    armed = production_monte_carlo_arm_authorized(repo_root) is True
    return _bind_result_core_from_bound(
        records, bound=bound, fixture=fixture, armed=armed
    )


def _require_canonical_production_records(
    records: Sequence[Mapping[str, Any]],
) -> list[Mapping[str, Any]]:
    """Fail closed unless records are exactly the frozen 3200-job plan in order."""
    jobs = planned_production_jobs()
    if len(jobs) != PRODUCTION_PLANNED_TOTAL_WORLDS:
        _refuse("production world plan is not 3200 identities")
    if len(records) != PRODUCTION_PLANNED_TOTAL_WORLDS:
        _tamper("production world records count is not the frozen 3200-world plan")
    owned: list[Mapping[str, Any]] = []
    for rec, job in zip(records, jobs, strict=True):
        _record_job_identity(rec, *job)
        owned.append(_jsonable(dict(rec)))
    _require_unique_planned_set(owned)
    return owned


def _production_world_records_from_bound(
    records, *, bound: Mapping[str, str]
) -> dict[str, Any]:
    """Canonical WORLD_RECORDS evidence. Records are the authority, not aggregates."""
    jsonable_records = _require_canonical_production_records(records)
    body = {
        "schema_version": "1.0",
        "kind": WORLD_RECORDS_KIND,
        "unit_id": UNIT_ID,
        "durability_id": DURABILITY_ID,
        "canonical_path": CANONICAL_WORLD_RECORDS_PATH,
        "execution_head": bound["head_sha"],
        "execution_tree": bound["tree_sha"],
        "run_identity": _run_identity_from_bound(bound),
        "grid": frozen_production_grid(),
        "jobs": [list(job) for job in planned_production_jobs()],
        "planned_world_count": PRODUCTION_PLANNED_TOTAL_WORLDS,
        "observed_world_count": len(jsonable_records),
        "record_count": len(jsonable_records),
        "world_set_sha256": world_set_sha256(jsonable_records),
        "record_digest_chain": list(_ordered_record_digest_chain(jsonable_records)),
        "records": jsonable_records,
        "real_market_data_access_authorized": False,
        "b2_06_scientific_execution_authorized": False,
        "validation_2025_authorized": False,
        "oos_2026_authorized": False,
    }
    raw = canonical_json_bytes(_jsonable(body))
    payload = dict(body)
    payload["world_records_sha256"] = _sha256_bytes(raw)
    payload["world_records_size"] = len(raw)
    return payload


def bind_result_document(*args, **kwargs):
    """Removed public binder. Caller-supplied aggregates cannot mint a RESULT."""
    _refuse("caller-supplied aggregates cannot mint a production RESULT")


_LIVE_SESSIONS: dict[int, "_CanonicalExecutionSession"] = {}
_CAPABILITY_KEEPALIVE: dict[int, object] = {}
_CLOSED_SESSIONS: dict[int, "_CanonicalExecutionSession"] = {}
_CLOSED_CAPABILITY_KEEPALIVE: dict[int, object] = {}


class _CanonicalExecutionSession:
    """Module-private session storage. Constructing this class grants no authority."""

    __slots__ = (
        "repo_root",
        "production",
        "jobs",
        "run_identity",
        "bound",
        "reservation",
        "records",
        "record_digest_chain",
        "chain_secret",
        "chain_mac",
        "capability",
        "open",
        "completed",
        "evaluator",
        "partial_payload",
    )


def _register_session(session: _CanonicalExecutionSession) -> object:
    capability = object()
    session.capability = capability
    _LIVE_SESSIONS[id(capability)] = session
    _CAPABILITY_KEEPALIVE[id(capability)] = capability
    return capability


def _session_from_capability(capability: object) -> _CanonicalExecutionSession:
    session = _LIVE_SESSIONS.get(id(capability))
    if session is not None and session.capability is capability:
        if session.open is not True:
            _refuse("canonical session capability is stale")
        return session
    closed = _CLOSED_SESSIONS.get(id(capability))
    if closed is not None and closed.capability is capability:
        _refuse("canonical session capability is stale")
    _refuse("canonical session capability is not valid")


def _retire_session(session: _CanonicalExecutionSession) -> None:
    session.open = False
    cap = session.capability
    _LIVE_SESSIONS.pop(id(cap), None)
    _CAPABILITY_KEEPALIVE.pop(id(cap), None)
    _CLOSED_SESSIONS[id(cap)] = session
    _CLOSED_CAPABILITY_KEEPALIVE[id(cap)] = cap


def _close_session(session: _CanonicalExecutionSession) -> None:
    session.completed = True
    _retire_session(session)


def _fixture_jobs_forbidden_as_production(jobs: Sequence[tuple[str, int, int]]) -> None:
    planned = planned_production_jobs()
    if tuple(jobs) == planned:
        _refuse("fixture driver cannot encode the frozen production grid")
    if len(jobs) >= PRODUCTION_PLANNED_TOTAL_WORLDS:
        _refuse("fixture driver cannot encode the frozen production grid")
    production_n = {PRODUCTION_PRIMARY_N, *PRODUCTION_SMALL_N}
    for scenario_id, n_rows, world_index in jobs:
        if int(n_rows) in production_n:
            _refuse("fixture driver cannot encode production N")
        if int(world_index) < 0:
            _refuse("fixture world index is invalid")
        if not str(scenario_id):
            _refuse("fixture world identity is invalid")


def _terminal_production_result_present(repo_root: Path) -> bool:
    return _head_blob(repo_root, CANONICAL_RESULT_PATH) is not None


def _refuse_if_terminal_result_exists(repo_root: Path) -> None:
    if _terminal_production_result_present(repo_root):
        _refuse("production RESULT already exists; one-shot authority is consumed")


def _open_canonical_session(
    *,
    repo_root: Path,
    production: bool,
    jobs: tuple[tuple[str, int, int], ...],
    evaluator: Any | None,
) -> _CanonicalExecutionSession:
    bound = verify_executed_production_authority(repo_root)
    if production:
        frozen_production_grid()
        jobs = planned_production_jobs()
        if len(jobs) != PRODUCTION_PLANNED_TOTAL_WORLDS:
            _refuse("production world plan is not 3200 identities")
        _refuse_if_terminal_result_exists(repo_root)
    if production_monte_carlo_arm_authorized(repo_root) is not True:
        raise ProductionNotArmed(
            "SYNTHETIC_EXECUTION_NOT_AUTHORIZED: production_monte_carlo_arm_authorized=false"
        )
    if not production:
        _fixture_jobs_forbidden_as_production(jobs)
        if evaluator is None:
            _refuse("fixture driver requires an explicit non-production evaluator")
    for existing in _LIVE_SESSIONS.values():
        if existing.production and production and existing.open:
            _refuse("conflicting canonical production session is already open")
    session = _CanonicalExecutionSession()
    session.repo_root = repo_root
    session.production = bool(production)
    session.jobs = tuple(jobs)
    session.run_identity = canonical_run_identity(repo_root)
    session.bound = bound
    session.reservation = durable_reservation_document(repo_root)
    session.records = ()
    session.record_digest_chain = ()
    session.chain_secret = os.urandom(32)
    session.chain_mac = _mac_record_digest_chain(session.chain_secret, ())
    session.open = True
    session.completed = False
    session.evaluator = evaluator
    session.partial_payload = None
    _register_session(session)
    return session


def _record_job_identity(rec: Mapping[str, Any], scenario_id: str, n_rows: int, world_index: int) -> None:
    job = (str(scenario_id), int(n_rows), int(world_index))
    identity = world_identity(*job)
    if str(rec.get("scenario_id")) != job[0]:
        _refuse("canonical record scenario_id does not match planned job")
    if int(rec.get("n_rows", -1)) != job[1]:
        _refuse("canonical record n_rows does not match planned job")
    if int(rec.get("world_index", -1)) != job[2]:
        _refuse("canonical record world_index does not match planned job")
    if str(rec.get("world_identity", "")) != identity:
        _refuse("canonical record world identity does not match frozen plan")
    expected_seed = int(world_seed(identity))
    if int(rec.get("world_seed", -1)) != expected_seed:
        _refuse("canonical record world seed does not match frozen plan")
    if rec.get("stays_in_denominator") is not True:
        _refuse("canonical record must remain in the planned denominator")


def _append_session_record(
    session: _CanonicalExecutionSession, rec: Mapping[str, Any], job: tuple[str, int, int]
) -> None:
    _record_job_identity(rec, *job)
    owned = _jsonable(dict(rec))
    digest = _record_content_digest(owned)
    seen = {(str(item["scenario_id"]), int(item["n_rows"]), int(item["world_index"])) for item in session.records}
    if job in seen:
        _refuse("duplicate world identity")
    if job not in set(session.jobs):
        _refuse("extra world is not in the session plan")
    expected_index = len(session.records)
    if session.jobs[expected_index] != job:
        _refuse("canonical evaluation order drifted from the planned job list")
    session.records = tuple(session.records) + (_immutable_record(owned),)
    session.record_digest_chain = tuple(session.record_digest_chain) + (digest,)
    session.chain_mac = _mac_record_digest_chain(session.chain_secret, session.record_digest_chain)


def _evaluate_session_job(
    session: _CanonicalExecutionSession, scenario_id: str, n_rows: int, world_index: int
) -> Mapping[str, Any]:
    job = (str(scenario_id), int(n_rows), int(world_index))
    if session.production:
        rec = _evaluate_planned_world_body(scenario_id, n_rows, world_index)
    else:
        try:
            rec = session.evaluator(scenario_id, n_rows, world_index)
        except IncompleteWorld as exc:
            identity = world_identity(*job)
            rec = {
                "scenario_id": scenario_id,
                "n_rows": int(n_rows),
                "world_index": int(world_index),
                "world_identity": identity,
                "world_seed": int(world_seed(identity)),
                "valid": False,
                "invalid_reasons": (str(exc),),
                "stays_in_denominator": True,
            }
        if not isinstance(rec, Mapping):
            _refuse("fixture evaluator did not return a world record")
        rec = _jsonable(dict(rec))
    return rec


def _session_plan_integrity(session: _CanonicalExecutionSession) -> dict[str, Any]:
    planned = list(session.jobs)
    planned_set = set(planned)
    by_job: dict[tuple[str, int, int], Mapping[str, Any]] = {}
    for rec in session.records:
        job = (
            str(rec.get("scenario_id")),
            int(rec.get("n_rows", -1)),
            int(rec.get("world_index", -1)),
        )
        if job not in planned_set:
            _refuse("extra world is not in the session plan")
        if job in by_job:
            _refuse("duplicate world identity")
        _record_job_identity(rec, *job)
        by_job[job] = rec
    missing = [job for job in planned if job not in by_job]
    invalid_records = [rec for rec in session.records if rec.get("valid") is not True]
    return {
        "by_job": by_job,
        "missing": missing,
        "invalid_records": invalid_records,
        "incomplete_execution": bool(missing) or bool(invalid_records),
        "planned_world_count": len(planned),
        "observed_world_count": len(by_job),
    }


def _verify_session_record_chain(session: _CanonicalExecutionSession) -> None:
    recomputed = _ordered_record_digest_chain(session.records)
    if recomputed != tuple(session.record_digest_chain):
        _refuse("canonical record content digest chain mismatch")
    expected_mac = _mac_record_digest_chain(session.chain_secret, recomputed)
    if expected_mac != session.chain_mac:
        _refuse("canonical record content digest chain mismatch")


def _result_envelope_from_core(core: Mapping[str, Any]) -> dict[str, Any]:
    core_bytes = canonical_json_bytes(_jsonable(core))
    return {
        "core": core,
        "core_sha256": _sha256_bytes(core_bytes),
        "core_size": len(core_bytes),
    }


def _mint_from_session(session: _CanonicalExecutionSession) -> dict[str, Any]:
    _verify_session_record_chain(session)
    integrity = _session_plan_integrity(session)
    if integrity["incomplete_execution"]:
        if session.production:
            aggregates = aggregate_planned_worlds(session.records)
            if aggregates["mechanical_conclusion"] != "INCOMPLETE_EXECUTION_NO_METHODOLOGY_CLAIM":
                _refuse(
                    "incomplete execution cannot mint a final RESULT: "
                    "INCOMPLETE_EXECUTION_NO_METHODOLOGY_CLAIM"
                )
        _refuse(
            "incomplete execution cannot mint a final RESULT: "
            "INCOMPLETE_EXECUTION_NO_METHODOLOGY_CLAIM"
        )
    if session.production:
        if integrity["planned_world_count"] != PRODUCTION_PLANNED_TOTAL_WORLDS:
            _refuse("production world plan is not 3200 identities")
        aggregates = aggregate_planned_worlds(session.records)
        if (
            aggregates["incomplete_execution"]
            or aggregates["observed_world_count"] != PRODUCTION_PLANNED_TOTAL_WORLDS
            or aggregates["mechanical_conclusion"] == "INCOMPLETE_EXECUTION_NO_METHODOLOGY_CLAIM"
        ):
            _refuse("incomplete execution cannot mint a final RESULT")
        authenticate_cached_world_records_from_frozen_execution(
            planned=session.jobs,
            records=session.records,
            repo_root=session.repo_root,
            production=True,
            workers=resolve_verification_workers(None),
        )
        bound = verify_executed_production_authority(session.repo_root)
        core = _bind_result_core(
            records=session.records,
            repo_root=session.repo_root,
            fixture=False,
        )
        envelope = _result_envelope_from_core(core)
        world_records = _production_world_records_from_bound(
            session.records, bound=bound
        )
        _close_session(session)
        return {"result": envelope, "world_records": world_records}
    core = _bind_result_core(
        records=session.records,
        repo_root=session.repo_root,
        fixture=True,
    )
    envelope = _result_envelope_from_core(core)
    _close_session(session)
    return envelope


def _attach_partial_payload(exc: BaseException, partial: Mapping[str, Any] | None) -> None:
    if partial is None:
        return
    try:
        setattr(exc, "_canonical_partial", partial)
    except Exception:
        return


def _abort_session(session: _CanonicalExecutionSession, exc: BaseException) -> None:
    partial = None
    if session.production and session.records:
        try:
            partial = persist_partial_worlds(session.records)
            session.partial_payload = partial
        except Exception:
            partial = None
    _attach_partial_payload(exc, partial)
    if session.capability is not None and id(session.capability) in _LIVE_SESSIONS:
        _retire_session(session)


def _run_session_jobs(
    session: _CanonicalExecutionSession, *, workers: int = 1
) -> dict[str, Any]:
    workers_n = resolve_execution_workers(workers)
    try:
        if session.production:
            if os.environ.get("HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1_TEST_WORKER_CRASH"):
                _refuse("test worker crash injection cannot enter production")
            if os.environ.get("HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1_VERIFY_STAGGER_MS"):
                _refuse("verification stagger cannot enter production")
            _refuse_production_durability_hooks()
            store = DurablePartialWorldStore.open(
                session.repo_root / DURABLE_PARTIAL_REL,
                bound=session.bound,
                planned=session.jobs,
                repo_root=session.repo_root,
            )
            records = evaluate_planned_jobs_fail_closed(
                session.jobs, workers=workers_n, durable_partial=store
            )
            for job, rec in zip(session.jobs, records):
                _append_session_record(session, rec, job)
        else:
            for job in session.jobs:
                rec = _evaluate_session_job(session, *job)
                _append_session_record(session, rec, job)
        return _mint_from_session(session)
    except SyntheticExecutionNotAuthorized:
        if session.capability is not None and id(session.capability) in _LIVE_SESSIONS:
            _retire_session(session)
        raise
    except BaseException as exc:
        _abort_session(session, exc)
        raise


def open_canonical_fixture_session(
    jobs: Sequence[tuple[str, int, int]],
    world_evaluator,
    *args: Any,
    **kwargs: Any,
) -> object:
    if args or kwargs:
        _refuse("caller arguments cannot authorize the fixture driver")
    root = _repo_root()
    session = _open_canonical_session(
        repo_root=root,
        production=False,
        jobs=tuple((str(s), int(n), int(i)) for s, n, i in jobs),
        evaluator=world_evaluator,
    )
    return session.capability


def evaluate_canonical_session_job(
    capability: object,
    scenario_id: str,
    n_rows: int,
    world_index: int,
    *args: Any,
    **kwargs: Any,
) -> Mapping[str, Any]:
    if args or kwargs:
        _refuse("caller arguments cannot authorize canonical evaluation")
    session = _session_from_capability(capability)
    try:
        job = (str(scenario_id), int(n_rows), int(world_index))
        rec = _evaluate_session_job(session, *job)
        _append_session_record(session, rec, job)
        return rec
    except SyntheticExecutionNotAuthorized:
        raise
    except BaseException as exc:
        _abort_session(session, exc)
        raise


def abandon_canonical_session(capability: object, *args: Any, **kwargs: Any) -> None:
    """Mark a live session crashed/abandoned. Cannot mint afterwards."""
    if args or kwargs:
        _refuse("caller arguments cannot authorize session abandonment")
    session = _session_from_capability(capability)
    if session.production and session.records:
        persist_partial_worlds(session.records)
    _retire_session(session)


def run_canonical_production_execution(*args: Any, **kwargs: Any) -> dict[str, Any]:
    """Canonical 3200-world driver. Requires ARM. Never accepts caller records.

    Worker count is not a caller kwarg. Isolated production reads
    HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1_WORKERS (default 1).
    """
    if args or kwargs:
        _refuse("caller arguments cannot authorize production execution")
    workers_n = resolve_execution_workers(None)
    root = _repo_root()
    verify_executed_production_authority(root)
    session = _open_canonical_session(
        repo_root=root,
        production=True,
        jobs=planned_production_jobs(),
        evaluator=None,
    )
    return _run_session_jobs(session, workers=workers_n)


def run_canonical_fixture_driver(
    jobs: Sequence[tuple[str, int, int]],
    world_evaluator,
    *args: Any,
    **kwargs: Any,
) -> dict[str, Any]:
    """Test-only orchestration over an explicit non-production plan.

    Requires the same verify/ARM/reservation/session capability path. Cannot
    encode the frozen 3200-world production grid or production N.
    """
    if args or kwargs:
        _refuse("caller arguments cannot authorize the fixture driver")
    root = _repo_root()
    verify_executed_production_authority(root)
    session = _open_canonical_session(
        repo_root=root,
        production=False,
        jobs=tuple((str(s), int(n), int(i)) for s, n, i in jobs),
        evaluator=world_evaluator,
    )
    return _run_session_jobs(session)


def mint_session_result(capability: object, *args: Any, **kwargs: Any) -> dict[str, Any]:
    """Mint from a live canonical session capability only."""
    if args or kwargs:
        _refuse("caller arguments cannot authorize a production RESULT")
    session = _session_from_capability(capability)
    try:
        return _mint_from_session(session)
    except SyntheticExecutionNotAuthorized:
        raise
    except BaseException as exc:
        _abort_session(session, exc)
        raise


def mint_final_result(*args: Any, **kwargs: Any):
    if kwargs:
        _refuse("caller arguments cannot authorize a production RESULT")
    if args:
        _refuse("caller-supplied records cannot mint a production RESULT")
    _refuse("caller-supplied records cannot mint a production RESULT")


def _parse_result_envelope(document) -> tuple[Mapping[str, Any], bytes]:
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
    return core, core_bytes


def _assert_result_core_matches_expected(
    core: Mapping[str, Any], core_bytes: bytes, expected: Mapping[str, Any]
) -> None:
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
    if "claim_sha256" in expected and core.get("claim_sha256") != expected["claim_sha256"]:
        raise ProductionIntegrityError(
            "SYNTHETIC_EXECUTION_NOT_AUTHORIZED: claim digest is not tracked authority"
        )
    if "aggregates" in expected and core.get("aggregates") != expected["aggregates"]:
        raise ProductionIntegrityError(
            "SYNTHETIC_EXECUTION_NOT_AUTHORIZED: aggregates were not derived from the world set"
        )
    if core.get("record_digest_chain") != expected.get("record_digest_chain"):
        raise ProductionIntegrityError(
            "SYNTHETIC_EXECUTION_NOT_AUTHORIZED: world_set_sha256 tamper detected"
        )
    if core.get("mechanical_conclusion") != expected.get("mechanical_conclusion"):
        raise ProductionIntegrityError(
            "SYNTHETIC_EXECUTION_NOT_AUTHORIZED: core payload tamper detected"
        )
    if core_bytes != expected_bytes:
        raise ProductionIntegrityError(
            "SYNTHETIC_EXECUTION_NOT_AUTHORIZED: core payload tamper detected"
        )


def verify_bound_result_document(document, records, *args, **kwargs):
    """LIVE / execution-context RESULT verification against current HEAD.

    Reconstructs the expected core from caller-supplied records and the live
    execution checkout. After a later RESULT commit, current HEAD is not the
    execution commit; use `verify_bound_result_from_tracked_authority`.
    """
    if args or kwargs:
        _refuse("caller arguments cannot authorize result verification")
    core, core_bytes = _parse_result_envelope(document)
    expected = _bind_result_core(
        records=records,
        repo_root=_repo_root(),
        fixture=core.get("fixture") is True or core.get("not_a_production_result") is True,
    )
    _assert_result_core_matches_expected(core, core_bytes, expected)


def _load_result_document(result_document_or_path, repo_root: Path) -> tuple[dict[str, Any], bytes]:
    if result_document_or_path is None:
        blob = _head_blob(repo_root, CANONICAL_RESULT_PATH)
        if blob is None:
            _refuse("tracked RESULT artifact is absent")
        try:
            payload = json.loads(blob.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise SyntheticExecutionNotAuthorized(
                "SYNTHETIC_EXECUTION_NOT_AUTHORIZED: malformed tracked RESULT artifact"
            ) from exc
        if not isinstance(payload, dict):
            _refuse("malformed tracked RESULT artifact")
        return payload, blob
    if isinstance(result_document_or_path, (str, Path)):
        path = Path(result_document_or_path)
        if not path.is_absolute():
            path = repo_root / path
        if path.resolve() == (repo_root / CANONICAL_RESULT_PATH).resolve():
            blob = _head_blob(repo_root, CANONICAL_RESULT_PATH)
            if blob is None:
                _refuse("tracked RESULT artifact is absent")
            try:
                payload = json.loads(blob.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise SyntheticExecutionNotAuthorized(
                    "SYNTHETIC_EXECUTION_NOT_AUTHORIZED: malformed tracked RESULT artifact"
                ) from exc
            if not isinstance(payload, dict):
                _refuse("malformed tracked RESULT artifact")
            return payload, blob
        blob = path.read_bytes()
        try:
            payload = json.loads(blob.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise SyntheticExecutionNotAuthorized(
                "SYNTHETIC_EXECUTION_NOT_AUTHORIZED: malformed RESULT artifact"
            ) from exc
        if not isinstance(payload, dict):
            _refuse("malformed RESULT artifact")
        return payload, blob
    if isinstance(result_document_or_path, Mapping):
        payload = dict(result_document_or_path)
        return payload, canonical_json_bytes(_jsonable(payload))
    _refuse("RESULT document is not a mapping or path")


def _require_docs_only_descendants(repo_root: Path, *, ancestor: str) -> None:
    head = _head_sha(repo_root)
    if ancestor == head:
        return
    if not _is_ancestor(repo_root, ancestor, head):
        _refuse("execution commit is not an ancestor of current HEAD")
    commit = head
    walked = 0
    while commit != ancestor:
        if _commit_changes_execution_authority(repo_root, commit):
            _refuse(
                "commits after execution are not docs-only; historical RESULT authority is refused"
            )
        parent = _parent_sha_of(repo_root, commit)
        if parent is None:
            _refuse("execution commit is not an ancestor of current HEAD")
        commit = parent
        walked += 1
        if walked > 10000:
            _refuse("historical RESULT ancestry walk exceeded bound")


def _tracked_result_blobs(repo_root: Path) -> list[bytes]:
    proc = subprocess.run(
        ["git", "-C", str(repo_root), "log", "--pretty=%H", "--", CANONICAL_RESULT_PATH],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if proc.returncode != 0:
        _refuse("git log of RESULT path failed")
    blobs: list[bytes] = []
    for commit in proc.stdout.decode("ascii").split():
        blob = _commit_blob(repo_root, commit, CANONICAL_RESULT_PATH)
        if blob is not None:
            blobs.append(blob)
    return blobs


def _terminal_result_commit(repo_root: Path, document_bytes: bytes) -> str:
    """Commit that tracks the verified RESULT blob. Later docs-only HEAD is not identity."""
    proc = subprocess.run(
        ["git", "-C", str(repo_root), "log", "--pretty=%H", "--", CANONICAL_RESULT_PATH],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if proc.returncode != 0:
        _refuse("git log of RESULT path failed")
    for commit in proc.stdout.decode("ascii").split():
        blob = _commit_blob(repo_root, commit, CANONICAL_RESULT_PATH)
        if blob == document_bytes:
            return commit.strip().lower()
    _refuse("terminal RESULT commit cannot be located")


def _refuse_conflicting_terminal_result(repo_root: Path, document_bytes: bytes) -> None:
    blobs = _tracked_result_blobs(repo_root)
    unique = set(blobs)
    if len(unique) > 1:
        _refuse("duplicate/conflicting terminal production RESULT")
    if unique and document_bytes not in unique:
        _refuse("RESULT document does not match tracked artifact")


def _tamper(detail: str) -> None:
    raise ProductionIntegrityError(f"SYNTHETIC_EXECUTION_NOT_AUTHORIZED: {detail}")


def _canonical_equal(left: Any, right: Any) -> bool:
    return canonical_json_bytes(_jsonable(left)) == canonical_json_bytes(_jsonable(right))


def _assert_production_protected_literals(core: Mapping[str, Any]) -> None:
    for key in PRODUCTION_FORBIDDEN_CORE_KEYS:
        if key in core:
            _tamper(f"production RESULT core must not declare {key}")
    for key, expected in PRODUCTION_PROTECTED_CORE_LITERALS.items():
        if core.get(key) is not expected:
            _tamper(f"protected scope authorization flag tamper detected: {key}")


def _load_tracked_world_records(
    repo_root: Path, core: Mapping[str, Any], bound: Mapping[str, str]
) -> tuple[bytes, dict[str, Any], list[Mapping[str, Any]]]:
    """Load tracked WORLD_RECORDS from git objects as retained evidence.

    Worktree bytes are not authority. Record bodies are not scientific inputs.
    The authoritative verifier independently recomputes the 3200 worlds and
    compares this artifact; it does not treat the tracked records as the
    frozen experiment.
    """
    blob = _head_blob(repo_root, CANONICAL_WORLD_RECORDS_PATH)
    if blob is None:
        _refuse(
            "tracked production WORLD_RECORDS artifact is absent; "
            "scientific payload cannot be verified"
        )
    if core.get("records_artifact_path") != CANONICAL_WORLD_RECORDS_PATH:
        _tamper("records_artifact_path is not the canonical WORLD_RECORDS path")
    if core.get("records_artifact_sha256") != _sha256_bytes(blob):
        _tamper("records_artifact_sha256 does not match tracked WORLD_RECORDS bytes")
    if core.get("records_artifact_size") != len(blob):
        _tamper("records_artifact_size does not match tracked WORLD_RECORDS bytes")
    try:
        payload = json.loads(blob.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SyntheticExecutionNotAuthorized(
            "SYNTHETIC_EXECUTION_NOT_AUTHORIZED: malformed tracked WORLD_RECORDS artifact"
        ) from exc
    if not isinstance(payload, dict):
        _refuse("malformed tracked WORLD_RECORDS artifact")
    body = {
        key: value
        for key, value in payload.items()
        if key not in {"world_records_sha256", "world_records_size"}
    }
    raw = canonical_json_bytes(_jsonable(body))
    if payload.get("world_records_sha256") != _sha256_bytes(raw):
        _tamper("production WORLD_RECORDS digest mismatch")
    if payload.get("world_records_size") != len(raw):
        _tamper("production WORLD_RECORDS size mismatch")
    if payload.get("kind") != WORLD_RECORDS_KIND:
        _tamper("production WORLD_RECORDS kind is not canonical")
    if payload.get("canonical_path") != CANONICAL_WORLD_RECORDS_PATH:
        _tamper("production WORLD_RECORDS path is not canonical")
    if payload.get("execution_head") != bound["head_sha"]:
        _tamper("production WORLD_RECORDS execution_head does not match the RESULT")
    if payload.get("execution_tree") != bound["tree_sha"]:
        _tamper("production WORLD_RECORDS execution_tree does not match the RESULT")
    if payload.get("run_identity") != _run_identity_from_bound(bound):
        _tamper("production WORLD_RECORDS run_identity does not match the RESULT")
    if not _canonical_equal(payload.get("grid"), frozen_production_grid()):
        _tamper("production WORLD_RECORDS grid is not frozen authority")
    expected_jobs = [list(job) for job in planned_production_jobs()]
    if not _canonical_equal(payload.get("jobs"), expected_jobs):
        _tamper("production WORLD_RECORDS job plan is not the frozen 3200-world plan")
    records = payload.get("records")
    if not isinstance(records, list):
        _tamper("production WORLD_RECORDS records are missing")
    owned = _require_canonical_production_records(records)
    if payload.get("planned_world_count") != PRODUCTION_PLANNED_TOTAL_WORLDS:
        _tamper("production WORLD_RECORDS planned_world_count is not the frozen 3200-world plan")
    if payload.get("observed_world_count") != PRODUCTION_PLANNED_TOTAL_WORLDS:
        _tamper("production WORLD_RECORDS observed_world_count is not the frozen 3200-world plan")
    if payload.get("record_count") != PRODUCTION_PLANNED_TOTAL_WORLDS:
        _tamper("production WORLD_RECORDS record_count is not the frozen 3200-world plan")
    recomputed_chain = list(_ordered_record_digest_chain(owned))
    recomputed_world = world_set_sha256(owned)
    if payload.get("world_set_sha256") != recomputed_world:
        _tamper("WORLD_RECORDS world_set_sha256 was not derived from the records")
    if not _canonical_equal(payload.get("record_digest_chain"), recomputed_chain):
        _tamper("WORLD_RECORDS record_digest_chain was not derived from the records")
    if core.get("world_set_sha256") != recomputed_world:
        _tamper("world_set_sha256 tamper detected")
    if not _canonical_equal(core.get("record_digest_chain"), recomputed_chain):
        _tamper("record_digest_chain tamper detected")
    if core.get("record_count") != PRODUCTION_PLANNED_TOTAL_WORLDS:
        _tamper("record_count is not the frozen 3200-world plan")
    return blob, payload, owned


def _assert_historical_recompute_uses_authorized_code(
    repo_root: Path, bound: Mapping[str, str]
) -> None:
    """Prove the executing modules are the historically authorized execution blobs.

    Historical recomputation must not run current-HEAD science against an old
    RESULT. Executing lib/runner/auth/production bytes must equal the git
    objects at `execution_head`.
    """
    execution_head = bound["head_sha"]
    for rel in EXECUTION_AUTHORITY_PATHS:
        historical = _commit_blob(repo_root, execution_head, rel)
        if historical is None:
            if rel == WORKER_REL:
                continue
            _tamper(f"historical recomputation authority missing at execution_head: {rel}")
        executing = _executing_file(rel).read_bytes()
        if executing != historical:
            _tamper(
                "historical recomputation is not executing the authorized execution blobs"
            )
        if bound.get(rel) != _sha256_bytes(historical):
            _tamper("historical recomputation bound digest does not match execution blobs")
        if rel == LIB_REL and _sha256_bytes(executing) != FROZEN_REVIEWED_LIB_SHA256:
            _tamper("historical recomputation lib is not the frozen reviewed implementation")
    for rel, key in (
        (PREREG_JSON_REL, "prereg_json_sha256"),
        (PREREG_MD_REL, "prereg_md_sha256"),
    ):
        historical = _commit_blob(repo_root, execution_head, rel)
        if historical is None or _sha256_bytes(historical) != bound[key]:
            _tamper("historical recomputation prereg does not match execution authority")


def _recompute_production_records_from_frozen_execution(
    bound: Mapping[str, str],
) -> list[Mapping[str, Any]]:
    """Independently recompute all 3200 canonical production world bodies.

    Uses the frozen planned job set and `_evaluate_jobs_for_verification`
    (world-parallel spawn over `_evaluate_planned_world_body` when workers>1).
    Worker count is operational and must not change scientific output. Does not
    require live ARM. Does not mint, write artifacts, or consume one-shot
    authority. Tracked WORLD_RECORDS bodies are not inputs.
    """
    jobs = planned_production_jobs()
    if len(jobs) != PRODUCTION_PLANNED_TOTAL_WORLDS:
        _refuse("production world plan is not 3200 identities")
    if jobs[0] != ("NULL", 5000, 0) or jobs[-1] != ("SMALL", 10000, 399):
        _refuse("production world plan identity order drifted")
    records = _evaluate_jobs_for_verification(
        jobs, resolve_verification_workers(None)
    )
    for rec, job in zip(records, jobs, strict=True):
        scenario_id, n_rows, world_index = job
        identity = world_identity(scenario_id, int(n_rows), int(world_index))
        if str(rec.get("world_identity", "")) != identity:
            _tamper("recomputed world identity does not match the frozen plan")
        if int(rec.get("world_seed", -1)) != int(world_seed(identity)):
            _tamper("recomputed world seed does not match the frozen plan")
    return _require_canonical_production_records(records)


def _compare_recomputed_world_records(
    *,
    tracked_blob: bytes,
    tracked_records: Sequence[Mapping[str, Any]],
    recomputed_records: Sequence[Mapping[str, Any]],
    bound: Mapping[str, str],
) -> dict[str, Any]:
    """Fail closed unless tracked WORLD_RECORDS match independent recomputation."""
    expected_artifact = _production_world_records_from_bound(
        recomputed_records, bound=bound
    )
    expected_blob = canonical_json_bytes(_jsonable(expected_artifact))
    if not _canonical_equal(tracked_records, recomputed_records):
        _tamper("tracked WORLD_RECORDS were not produced by frozen execution")
    if tracked_blob != expected_blob:
        _tamper("tracked WORLD_RECORDS were not produced by frozen execution")
    return expected_artifact


def diagnose_historical_result_spotcheck(
    repo_root: Path | None = None,
    result_document_or_path: Mapping[str, Any] | str | Path | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """NON-AUTHORITATIVE diagnostic. Must not mint or validate durable claims.

    This is a developer/CI convenience only. It is not historical verification,
    not cryptographic authenticity, and not a substitute for full 3200-world
    recomputation. `durable_result_claim_from_tracked_authority` never calls it.
    Sampling is a fixed prefix of the frozen plan, not a `run_identity` secret.
    Operators must not replace full isolated `FULL_3200_RECOMPUTATION` with
    this diagnostic because the authoritative path is intentionally expensive.
    """
    if kwargs:
        _refuse("caller arguments cannot authorize a historical spot-check")
    root = Path(repo_root) if repo_root is not None else _repo_root()
    verify_executed_production_authority(root)
    document, _document_bytes = _load_result_document(result_document_or_path, root)
    core, _core_bytes = _parse_result_envelope(document)
    if core.get("fixture") is True or core.get("not_a_production_result") is True:
        _refuse("spot-check diagnostic does not apply to fixture RESULT documents")
    execution_head = str(core.get("execution_head") or "").strip().lower()
    bound = verify_historical_execution_authority(
        repo_root=root, execution_commit=execution_head
    )
    _blob, _payload, tracked = _load_tracked_world_records(root, core, bound)
    jobs = planned_production_jobs()[:8]
    mismatches: list[dict[str, Any]] = []
    for scenario_id, n_rows, world_index in jobs:
        recomputed = _jsonable(_evaluate_planned_world_body(scenario_id, n_rows, world_index))
        job = (str(scenario_id), int(n_rows), int(world_index))
        tracked_rec = next(
            (
                rec
                for rec in tracked
                if (
                    str(rec.get("scenario_id")),
                    int(rec.get("n_rows", -1)),
                    int(rec.get("world_index", -1)),
                )
                == job
            ),
            None,
        )
        if tracked_rec is None or not _canonical_equal(tracked_rec, recomputed):
            mismatches.append({"job": [scenario_id, n_rows, world_index], "mismatch": True})
    return {
        "authoritative": False,
        "authoritative_historical_verification": False,
        "durable_claim_authorized": False,
        "full_recompute": False,
        "n_checked": len(jobs),
        "mismatches": mismatches,
        "note": "spot-check is not historical verification and cannot mint a durable claim",
    }



def _assert_historical_production_identity(
    core: Mapping[str, Any], bound: Mapping[str, str]
) -> None:
    reservation = _durable_reservation_from_bound(bound)
    claim = _durable_claim_from_bound(bound)
    expected_auth = _authority_sha256_from_bound(bound)
    if core.get("execution_head") != bound["head_sha"]:
        raise ProductionIntegrityError(
            "SYNTHETIC_EXECUTION_NOT_AUTHORIZED: execution_head tamper detected"
        )
    if core.get("execution_tree") != bound["tree_sha"]:
        raise ProductionIntegrityError(
            "SYNTHETIC_EXECUTION_NOT_AUTHORIZED: execution_tree tamper detected"
        )
    if core.get("run_identity") != _run_identity_from_bound(bound):
        raise ProductionIntegrityError(
            "SYNTHETIC_EXECUTION_NOT_AUTHORIZED: run_identity tamper detected"
        )
    if core.get("reservation_sha256") != _sha256_bytes(canonical_json_bytes(reservation)):
        raise ProductionIntegrityError(
            "SYNTHETIC_EXECUTION_NOT_AUTHORIZED: reservation digest is not tracked authority"
        )
    if core.get("claim_sha256") != _sha256_bytes(canonical_json_bytes(claim)):
        raise ProductionIntegrityError(
            "SYNTHETIC_EXECUTION_NOT_AUTHORIZED: claim digest is not tracked authority"
        )
    if core.get("authority_sha256") != expected_auth:
        raise ProductionIntegrityError(
            "SYNTHETIC_EXECUTION_NOT_AUTHORIZED: production blob differs from bound digest"
        )
    if core.get("frozen_lib_sha256") != bound[LIB_REL]:
        raise ProductionIntegrityError(
            "SYNTHETIC_EXECUTION_NOT_AUTHORIZED: frozen lib identity tamper detected"
        )
    if core.get("prereg_json_sha256") != bound["prereg_json_sha256"]:
        raise ProductionIntegrityError(
            "SYNTHETIC_EXECUTION_NOT_AUTHORIZED: prereg json identity tamper detected"
        )
    if core.get("prereg_md_sha256") != bound["prereg_md_sha256"]:
        raise ProductionIntegrityError(
            "SYNTHETIC_EXECUTION_NOT_AUTHORIZED: prereg md identity tamper detected"
        )
    if core.get("production_monte_carlo_arm_authorized") is not True:
        raise ProductionIntegrityError(
            "SYNTHETIC_EXECUTION_NOT_AUTHORIZED: historical RESULT ARM field tamper detected"
        )


def _require_hex_token(value: object, *, label: str, length: int) -> str:
    if not isinstance(value, str) or len(value) != length:
        _tamper(f"isolated historical recompute proof {label} is not a {length}-hex token")
    if any(ch not in "0123456789abcdef" for ch in value):
        _tamper(f"isolated historical recompute proof {label} is not a {length}-hex token")
    return value


def _isolated_child_stderr_text(completed: subprocess.CompletedProcess) -> str:
    stderr = completed.stderr
    if stderr is None:
        return ""
    if isinstance(stderr, bytes):
        return stderr.decode("utf-8", "replace")
    return str(stderr)


def _fail_closed_isolated_historical_recompute(
    completed: subprocess.CompletedProcess,
) -> None:
    detail = _isolated_child_stderr_text(completed).strip()
    if not detail:
        _refuse(
            f"isolated historical recompute child failed (exit {int(completed.returncode)})"
        )
    first = detail.splitlines()[0]
    for line in detail.splitlines():
        if line.startswith("SYNTHETIC_EXECUTION_NOT_AUTHORIZED"):
            raise SyntheticExecutionNotAuthorized(line)
    _refuse(f"isolated historical recompute child failed: {first}")


def _parse_historical_recompute_proof(stdout: bytes) -> dict[str, Any]:
    if not stdout:
        _refuse("isolated historical recompute child produced no proof")
    try:
        text = stdout.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise SyntheticExecutionNotAuthorized(
            "SYNTHETIC_EXECUTION_NOT_AUTHORIZED: isolated historical recompute proof is not UTF-8"
        ) from exc
    try:
        payload, idx = json.JSONDecoder().raw_decode(text)
    except json.JSONDecodeError as exc:
        raise SyntheticExecutionNotAuthorized(
            "SYNTHETIC_EXECUTION_NOT_AUTHORIZED: isolated historical recompute proof is not JSON"
        ) from exc
    if text[idx:].strip():
        _refuse("isolated historical recompute child produced duplicate or trailing output")
    if not isinstance(payload, dict):
        _refuse("isolated historical recompute proof is not an object")
    if frozenset(payload) != _HISTORICAL_RECOMPUTE_PROOF_KEYS:
        _refuse("isolated historical recompute proof keys are not canonical")
    if payload.get("schema_version") != "1.0":
        _refuse("isolated historical recompute proof schema is not canonical")
    if payload.get("kind") != HISTORICAL_RECOMPUTE_PROOF_KIND:
        _refuse("isolated historical recompute proof kind is not canonical")
    if payload.get("mode") != HISTORICAL_RECOMPUTE_MODE:
        _refuse("isolated historical recompute proof mode is not canonical")
    if payload.get("verification") != AUTHORITATIVE_HISTORICAL_VERIFICATION:
        _refuse("isolated historical recompute proof is not FULL_3200_RECOMPUTATION")
    if payload.get("verification_success") is not True:
        _refuse("isolated historical recompute proof did not attest success")
    return payload


def _bind_historical_recompute_proof(
    proof: Mapping[str, Any],
    *,
    repo_root: Path,
    core: Mapping[str, Any],
    document_bytes: bytes,
) -> None:
    execution_head = _require_hex_token(
        proof.get("execution_head"), label="execution_head", length=40
    )
    execution_tree = _require_hex_token(
        proof.get("execution_tree"), label="execution_tree", length=40
    )
    run_identity = _require_hex_token(
        proof.get("run_identity"), label="run_identity", length=64
    )
    result_digest = _require_hex_token(
        proof.get("result_artifact_sha256"), label="result_artifact_sha256", length=64
    )
    records_digest = _require_hex_token(
        proof.get("records_artifact_sha256"), label="records_artifact_sha256", length=64
    )
    recomputed_digest = _require_hex_token(
        proof.get("recomputed_world_records_sha256"),
        label="recomputed_world_records_sha256",
        length=64,
    )
    if not isinstance(proof.get("result_artifact_size"), int) or isinstance(
        proof.get("result_artifact_size"), bool
    ):
        _tamper("isolated historical recompute proof result size is invalid")
    if not isinstance(proof.get("records_artifact_size"), int) or isinstance(
        proof.get("records_artifact_size"), bool
    ):
        _tamper("isolated historical recompute proof records size is invalid")
    if proof["result_artifact_size"] != len(document_bytes):
        _tamper("isolated historical recompute proof does not bind this RESULT")
    if result_digest != _sha256_bytes(document_bytes):
        _tamper("isolated historical recompute proof does not bind this RESULT")
    if execution_head != core.get("execution_head"):
        _tamper("isolated historical recompute proof execution_head does not bind this RESULT")
    if execution_tree != core.get("execution_tree"):
        _tamper("isolated historical recompute proof execution_tree does not bind this RESULT")
    if run_identity != core.get("run_identity"):
        _tamper("isolated historical recompute proof run_identity does not bind this RESULT")
    tracked = _head_blob(repo_root, CANONICAL_WORLD_RECORDS_PATH)
    if tracked is None:
        _refuse(
            "tracked production WORLD_RECORDS artifact is absent; "
            "scientific payload cannot be verified"
        )
    if records_digest != _sha256_bytes(tracked):
        _tamper("isolated historical recompute proof does not bind tracked WORLD_RECORDS")
    if proof["records_artifact_size"] != len(tracked):
        _tamper("isolated historical recompute proof does not bind tracked WORLD_RECORDS")
    if records_digest != core.get("records_artifact_sha256"):
        _tamper("isolated historical recompute proof records digest does not bind this RESULT")
    if proof["records_artifact_size"] != core.get("records_artifact_size"):
        _tamper("isolated historical recompute proof records size does not bind this RESULT")
    if recomputed_digest != records_digest:
        _tamper("isolated historical recompute proof does not attest matching WORLD_RECORDS")


def _require_isolated_historical_recompute(
    repo_root: Path, *, core: Mapping[str, Any], document_bytes: bytes
) -> None:
    """Authoritative production recomputation must happen in a fresh child.

    The parent does not recompute science, does not accept caller-supplied
    evaluators/plans/seeds/aggregates/record bodies, and has no in-process
    fallback. Full 3200-world recomputation is intentionally expensive and
    synchronous; there is no timeout because it may take many hours.
    """
    try:
        completed = _spawn_isolated_child(
            HISTORICAL_RECOMPUTE_MODE,
            repo_root=repo_root,
            text=False,
            extra_env={
                VERIFY_WORKERS_ENV: str(resolve_verification_workers(None)),
            },
        )
    except OSError as exc:
        _refuse(f"isolated historical recompute child could not spawn: {exc}")
    if int(completed.returncode) != 0:
        _fail_closed_isolated_historical_recompute(completed)
    proof = _parse_historical_recompute_proof(completed.stdout or b"")
    _bind_historical_recompute_proof(
        proof, repo_root=repo_root, core=core, document_bytes=document_bytes
    )


def verify_bound_result_from_tracked_authority(
    repo_root: Path | None = None,
    result_document_or_path: Mapping[str, Any] | str | Path | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """TRACKED / historical RESULT verification.

    Authority is the RESULT core's embedded execution_head. Caller-supplied
    commits, records, or ARM flags cannot authorize. Current HEAD need not be
    armed; the named execution commit must have been correctly armed.

    Production verification does not recompute the 3200-world experiment in
    the caller process. It spawns `HISTORICAL_RECOMPUTE_MODE` through the
    existing isolated-child bootstrap. The child independently proves executing
    scientific/production blobs match `execution_head`, derives the frozen
    plan and seeds internally, recomputes all 3200 worlds, compares tracked
    WORLD_RECORDS evidence, and recomputes RESULT science. The parent treats
    a bound child success proof as the authoritative recomputation result and
    does not re-run or override science in-process. There is no in-process
    fallback. Spot-checks cannot satisfy this function. Full verification is
    intentionally expensive and synchronous.
    """
    if kwargs:
        _refuse("caller-supplied historical RESULT authority is refused")
    root = Path(repo_root) if repo_root is not None else _repo_root()
    verify_executed_production_authority(root)
    document, document_bytes = _load_result_document(result_document_or_path, root)
    core, core_bytes = _parse_result_envelope(document)
    execution_head = str(core.get("execution_head") or "").strip().lower()
    execution_tree = str(core.get("execution_tree") or "").strip().lower()
    if not execution_head or not execution_tree:
        _refuse("RESULT is missing execution commit/tree")
    if not _commit_exists(root, execution_head):
        _refuse("execution commit does not exist in git")
    if _commit_tree_sha(root, execution_head) != execution_tree:
        raise ProductionIntegrityError(
            "SYNTHETIC_EXECUTION_NOT_AUTHORIZED: execution tree does not match the named execution commit"
        )
    if not _is_ancestor(root, execution_head, _head_sha(root)):
        _refuse("execution commit is not an ancestor of current HEAD")
    _require_docs_only_descendants(root, ancestor=execution_head)
    bound = verify_historical_execution_authority(
        repo_root=root, execution_commit=execution_head
    )
    fixture = core.get("fixture") is True or core.get("not_a_production_result") is True
    if fixture:
        records = core.get("records")
        if not isinstance(records, list):
            _refuse("fixture RESULT is missing records required for historical reconstruction")
        expected = _bind_result_core_from_bound(
            records, bound=bound, fixture=True, armed=True
        )
        _assert_result_core_matches_expected(core, core_bytes, expected)
    else:
        # Production shape. Identity and a self-consistent WORLD_RECORDS
        # artifact are not scientific authority. Authoritative 3200-world
        # recomputation must occur in a fresh isolated child; the parent
        # never falls back to in-process evaluation.
        _assert_historical_production_identity(core, bound)
        _assert_production_protected_literals(core)
        if isinstance(core.get("records"), list):
            _tamper("production RESULT must not carry records as a substitute for WORLD_RECORDS")
        _require_isolated_historical_recompute(
            root, core=core, document_bytes=document_bytes
        )
    _refuse_conflicting_terminal_result(root, document_bytes)
    return _jsonable(dict(document))


def durable_result_claim_from_tracked_authority(
    repo_root: Path | None = None,
    result_document_or_path: Mapping[str, Any] | str | Path | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Return a #115-compatible RESULT claim after full historical verification.

    Does not write the worktree. Uncommitted claim files are not authority.
    Production claims explicitly bind RESULT and WORLD_RECORDS digest/size
    only after isolated `FULL_3200_RECOMPUTATION` succeeds. Claim minting
    therefore transitively requires the fresh historical-recompute child.
    There is no alternate claim path.
    """
    if kwargs:
        _refuse("caller arguments cannot authorize a durable RESULT claim")
    root = Path(repo_root) if repo_root is not None else _repo_root()
    verified = verify_bound_result_from_tracked_authority(root, result_document_or_path)
    core = verified["core"]
    bound = _bound_from_commit_blobs(root, str(core["execution_head"]))
    reservation = _durable_reservation_from_bound(bound)
    artifact_bytes = canonical_json_bytes(_jsonable(dict(verified)))
    terminal_commit = _terminal_result_commit(root, artifact_bytes)
    claim = {
        "schema_version": "1.0",
        "durability_id": DURABILITY_ID,
        "unit_id": UNIT_ID,
        "canonical_path": CANONICAL_CLAIM_PATH,
        "run_identity": core["run_identity"],
        "execution_head": core["execution_head"],
        "execution_tree": core["execution_tree"],
        "reservation_sha256": _sha256_bytes(canonical_json_bytes(reservation)),
        "artifact_kind": "result",
        "artifact_relative": CANONICAL_RESULT_PATH,
        "artifact_sha256": _sha256_bytes(artifact_bytes),
        "artifact_size": len(artifact_bytes),
        "result_artifact_sha256": _sha256_bytes(artifact_bytes),
        "result_artifact_size": len(artifact_bytes),
        "terminal_commit": terminal_commit,
        "terminal_tree": _commit_tree_sha(root, terminal_commit),
        "lifecycle": "TRACKED_RESULT_CLAIMED",
        "automatic_retry_authorized": False,
        "global_process_exclusion_claimed": False,
        "production_monte_carlo_arm_authorized": False,
        "production_calibration_executed": core.get("fixture") is not True,
        "final_result_minted": True,
    }
    if core.get("fixture") is not True:
        claim["records_artifact_path"] = CANONICAL_WORLD_RECORDS_PATH
        claim["records_artifact_sha256"] = core["records_artifact_sha256"]
        claim["records_artifact_size"] = core["records_artifact_size"]
    tracked = _head_blob(root, CANONICAL_CLAIM_PATH)
    if tracked is not None:
        try:
            existing = json.loads(tracked.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            _refuse("tracked durable claim cannot be verified")
        if existing != claim:
            _refuse("duplicate/conflicting durable RESULT claim")
        return existing
    return claim


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
        and "HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1_TEST_" not in key
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


def _spawn_isolated_child(
    mode, repo_root=None, *, text: bool = True, stdin=None, extra_env=None
):
    """Spawn the existing isolated interpreter. No timeout: historical
    `FULL_3200_RECOMPUTATION` is synchronous and may take many hours.
    Worker count is operational and is passed via extra_env, not as
    scientific authority.
    """
    root = (repo_root or _repo_root()).resolve()
    env = _isolated_child_env()
    if extra_env:
        for key, value in extra_env.items():
            env[str(key)] = str(value)
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
        env=env,
        check=False,
        capture_output=True,
        text=text,
        input=stdin,
    )


class CanonicalWorkerCapture:
    """Exact stdout capture from the isolated canonical production worker."""

    __slots__ = ("returncode", "stdout", "stderr", "stdout_bytes")

    def __init__(self, returncode: int, stdout_bytes: bytes, stderr: str):
        self.returncode = int(returncode)
        self.stdout_bytes = bytes(stdout_bytes)
        self.stdout = stdout_bytes.decode("utf-8", "surrogateescape")
        self.stderr = stderr

    def __eq__(self, other: object) -> bool:
        if isinstance(other, int):
            return self.returncode == other
        return NotImplemented

    def __int__(self) -> int:
        return self.returncode

    def __index__(self) -> int:
        return self.returncode


def canonical_worker_stdout_bytes(
    kind: str,
    payload: Mapping[str, Any],
    world_records: Mapping[str, Any] | None = None,
) -> bytes:
    if kind == WORKER_STDOUT_KIND_COMPLETE_RESULT:
        final = True
    elif kind == WORKER_STDOUT_KIND_PARTIAL:
        final = False
    else:
        _refuse("canonical worker stdout kind is not distinguished")
    envelope = {
        "schema_version": "1.0",
        "kind": kind,
        "final_result_minted": final,
        "payload": payload,
    }
    if kind == WORKER_STDOUT_KIND_COMPLETE_RESULT:
        if world_records is None:
            _refuse("canonical worker COMPLETE_RESULT must emit WORLD_RECORDS")
        envelope["world_records"] = world_records
    elif world_records is not None:
        _refuse("PARTIAL_NOT_RESULT cannot carry WORLD_RECORDS")
    return canonical_json_bytes(_jsonable(envelope))


def _emit_canonical_worker_stdout(
    kind: str,
    payload: Mapping[str, Any],
    world_records: Mapping[str, Any] | None = None,
) -> bytes:
    raw = canonical_worker_stdout_bytes(kind, payload, world_records)
    sys.stdout.buffer.write(raw)
    sys.stdout.flush()
    return raw


def spawn_canonical_production_process(*args, **kwargs):
    """Canonical production path: isolated interpreter, then re-verify, then refuse if unarmed."""
    if args or kwargs:
        _refuse("caller arguments cannot authorize production execution")
    proc = _spawn_isolated_child(WORKER_MODE, text=False)
    stdout_bytes = proc.stdout or b""
    stderr_text = (proc.stderr or b"").decode("utf-8", "surrogateescape")
    if stderr_text:
        sys.stderr.write(stderr_text)
    if stdout_bytes:
        sys.stdout.buffer.write(stdout_bytes)
        sys.stdout.flush()
    return CanonicalWorkerCapture(int(proc.returncode), stdout_bytes, stderr_text)


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
    armed = production_monte_carlo_arm_authorized()
    return {
        "module": __name__,
        "compose_gates": _jsonable(gates),
        "wilson_0_400": _jsonable(wilson_interval(0, 400)),
        "frozen_lib_sha256": FROZEN_REVIEWED_LIB_SHA256,
        "production_monte_carlo_arm_authorized": armed,
        "production_calibration_executed": False,
        "sys_path0": sys.path[0],
    }


def historical_recompute_worker_main() -> dict[str, Any]:
    """Fresh-process authoritative historical verification.

    Starts after the stdlib-only bootstrap and package import. Does not
    accept caller-supplied evaluators, plans, seeds, aggregates, record
    bodies, or module-path authority. Does not mint RESULT, write the
    worktree, or consume one-shot authority. Live ARM is not required.
    """
    if __name__ != "scripts.research.harness_synthetic_edge_calibration_v1_production":
        _refuse("historical-recompute child module is not the canonical package")
    root = _repo_root()
    verify_executed_production_authority(root)
    document, document_bytes = _load_result_document(None, root)
    core, core_bytes = _parse_result_envelope(document)
    if core.get("fixture") is True or core.get("not_a_production_result") is True:
        _refuse("historical-recompute child cannot verify fixture RESULT documents")
    execution_head = str(core.get("execution_head") or "").strip().lower()
    execution_tree = str(core.get("execution_tree") or "").strip().lower()
    if not execution_head or not execution_tree:
        _refuse("RESULT is missing execution commit/tree")
    if not _commit_exists(root, execution_head):
        _refuse("execution commit does not exist in git")
    if _commit_tree_sha(root, execution_head) != execution_tree:
        raise ProductionIntegrityError(
            "SYNTHETIC_EXECUTION_NOT_AUTHORIZED: execution tree does not match the named execution commit"
        )
    if not _is_ancestor(root, execution_head, _head_sha(root)):
        _refuse("execution commit is not an ancestor of current HEAD")
    _require_docs_only_descendants(root, ancestor=execution_head)
    bound = verify_historical_execution_authority(
        repo_root=root, execution_commit=execution_head
    )
    _assert_historical_production_identity(core, bound)
    _assert_production_protected_literals(core)
    if isinstance(core.get("records"), list):
        _tamper("production RESULT must not carry records as a substitute for WORLD_RECORDS")
    tracked_blob, _tracked_payload, tracked_records = _load_tracked_world_records(
        root, core, bound
    )
    _assert_historical_recompute_uses_authorized_code(root, bound)
    recomputed = _recompute_production_records_from_frozen_execution(bound)
    expected_artifact = _compare_recomputed_world_records(
        tracked_blob=tracked_blob,
        tracked_records=tracked_records,
        recomputed_records=recomputed,
        bound=bound,
    )
    expected = _bind_result_core_from_bound(
        recomputed, bound=bound, fixture=False, armed=True
    )
    _assert_result_core_matches_expected(core, core_bytes, expected)
    _refuse_conflicting_terminal_result(root, document_bytes)
    recomputed_blob = canonical_json_bytes(_jsonable(expected_artifact))
    return {
        "schema_version": "1.0",
        "kind": HISTORICAL_RECOMPUTE_PROOF_KIND,
        "mode": HISTORICAL_RECOMPUTE_MODE,
        "verification": AUTHORITATIVE_HISTORICAL_VERIFICATION,
        "verification_success": True,
        "execution_head": bound["head_sha"],
        "execution_tree": bound["tree_sha"],
        "run_identity": _run_identity_from_bound(bound),
        "result_artifact_sha256": _sha256_bytes(document_bytes),
        "result_artifact_size": len(document_bytes),
        "records_artifact_sha256": _sha256_bytes(tracked_blob),
        "records_artifact_size": len(tracked_blob),
        "recomputed_world_records_sha256": _sha256_bytes(recomputed_blob),
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
        if mode == HISTORICAL_RECOMPUTE_MODE:
            payload = historical_recompute_worker_main()
            sys.stdout.buffer.write(canonical_json_bytes(_jsonable(payload)))
            sys.stdout.flush()
            return 0
        if mode == AUTHENTICATE_CACHED_RECORDS_MODE:
            payload = authenticate_cached_records_worker_main()
            sys.stdout.buffer.write(canonical_json_bytes(_jsonable(payload)))
            sys.stdout.flush()
            return 0
        print("SYNTHETIC_EXECUTION_NOT_AUTHORIZED: unknown isolated child mode", file=sys.stderr)
        return 2
    except SyntheticExecutionNotAuthorized as exc:
        print(str(exc), file=sys.stderr)
        return 2


def fresh_process_worker_main():
    """Runs only inside a fresh isolated interpreter. Re-verifies, then drives if armed."""
    root = _repo_root()
    verify_executed_production_authority(root)
    frozen_production_grid()
    planned_production_jobs()
    if _terminal_production_result_present(root):
        print(
            "SYNTHETIC_EXECUTION_NOT_AUTHORIZED: production RESULT already exists; one-shot authority is consumed",
            file=sys.stderr,
        )
        return 2
    if production_monte_carlo_arm_authorized(root) is not True:
        print(
            "SYNTHETIC_EXECUTION_NOT_AUTHORIZED: production_monte_carlo_arm_authorized=false",
            file=sys.stderr,
        )
        return 2
    try:
        produced = run_canonical_production_execution()
        envelope = produced["result"]
        world_records = produced["world_records"]
        emitted = _emit_canonical_worker_stdout(
            WORKER_STDOUT_KIND_COMPLETE_RESULT, envelope, world_records
        )
        if not emitted:
            _refuse("canonical RESULT payload was not emitted")
        return 0
    except BaseException as exc:
        partial = getattr(exc, "_canonical_partial", None)
        if isinstance(partial, Mapping):
            _emit_canonical_worker_stdout(WORKER_STDOUT_KIND_PARTIAL, partial)
        if isinstance(exc, (KeyboardInterrupt, SystemExit)):
            raise
        if isinstance(exc, SyntheticExecutionNotAuthorized):
            print(str(exc), file=sys.stderr)
            return 2
        print(str(exc), file=sys.stderr)
        return 2


def production_durability_identity():
    state = inspect_production_arm_state()
    verifier_armed = production_monte_carlo_arm_authorized() is True
    armed = state["authorized"] is True
    if armed is not verifier_armed:
        _refuse("identity ARM state disagrees with the canonical ARM verifier")
    result_present = _head_blob(_repo_root(), CANONICAL_RESULT_PATH) is not None
    return {
        "stage": (
            "production_execution_driver_unarmed"
            if not armed
            else "production_monte_carlo_arm_authorized"
        ),
        "unit_id": UNIT_ID,
        "durability_id": DURABILITY_ID,
        "production_monte_carlo_arm_authorized": armed,
        "production_calibration_executed": False,
        "production_result_minted": result_present,
        "fresh_process_required": True,
        "durable_run_identity": True,
        "global_process_exclusion_claimed": False,
        "real_market_data_access_authorized": False,
        "b2_06_scientific_execution_authorized": False,
        "validation_2025_authorized": False,
        "oos_2026_authorized": False,
        "real_data_path": False,
        "monte_carlo_armed": armed,
        "authorization_consumed": result_present,
        "synthetic_execution_authorized": False,
        "canonical_paths": {
            "reservation": CANONICAL_RESERVATION_PATH,
            "claim": CANONICAL_CLAIM_PATH,
            "result": CANONICAL_RESULT_PATH,
            "partial": CANONICAL_PARTIAL_PATH,
            "durability": CANONICAL_DURABILITY_PATH,
            "arm": CANONICAL_ARM_PATH,
            "driver_freeze": CANONICAL_DRIVER_FREEZE_PATH,
            "world_records": CANONICAL_WORLD_RECORDS_PATH,
            "durable_partial_world_evidence": DURABLE_PARTIAL_REL,
        },
        "durable_partial_is_not_result": True,
        "durable_partial_is_not_world_records": True,
        "durable_partial_is_not_scientific_authority": True,
        "checkpoint_content_trusted_directly": False,
    }


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    print("SYNTHETIC_EXECUTION_NOT_AUTHORIZED", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
