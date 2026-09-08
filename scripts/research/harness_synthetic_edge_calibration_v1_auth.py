"""Tracked one-shot production authorization for HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1.

Authority is repository state: HEAD blobs, frozen implementation ancestry, and
the canonical tracked authorization artifact. Caller kwargs, environment
variables, and alternate paths cannot authorize execution.

This module does not run the 3200-world Monte Carlo. After a minted proof, the
unique production seam is reached and then stops without generating a RESULT.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

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
    SyntheticExecutionNotAuthorized,
    frozen_production_authority,
    load_frozen_prereg,
)

CANONICAL_AUTHORIZATION_PATH = (
    "docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1_EXECUTION_AUTHORIZATION.json"
)
CANONICAL_CLAIM_PATH = (
    "docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1_PRODUCTION_EXECUTION_CLAIM.json"
)
AUTHORIZATION_ID = (
    "HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1_ONE_SHOT_PRODUCTION_EXECUTION_V1"
)
LIFECYCLE_NOT_AUTHORIZED = "NOT_AUTHORIZED"
LIFECYCLE_AUTHORIZED_UNUSED = "AUTHORIZED_UNUSED"
LIFECYCLE_CONSUMED = "CONSUMED"
_MINT = object()

_FALSE_BOUNDARIES = (
    "real_market_data_access_authorized",
    "b2_06_scientific_execution_authorized",
    "validation_2025_authorized",
    "oos_2026_authorized",
)


class AuthorizationConsumed(SyntheticExecutionNotAuthorized):
    """The one-shot authorization has a durable consumed/result claim."""


class AuthorizedExecutionBoundaryReached(RuntimeError):
    """Minted authorization reached the Monte Carlo seam without executing it."""

    def __init__(self, proof: "VerifiedProductionAuthorization") -> None:
        self.proof = proof
        super().__init__("AUTHORIZED_UNUSED_PRODUCTION_EXECUTION_BOUNDARY")


@dataclass(frozen=True)
class VerifiedProductionAuthorization:
    authorization_id: str
    authorization_blob_sha256: str
    head_sha: str
    tree_sha: str
    unit_id: str
    grid: dict[str, Any]
    lifecycle: str
    _mint: object = field(repr=False, compare=False)

    def assert_minted(self) -> None:
        if self._mint is not _MINT:
            raise SyntheticExecutionNotAuthorized("SYNTHETIC_EXECUTION_NOT_AUTHORIZED")
        if self.unit_id != UNIT_ID or self.authorization_id != AUTHORIZATION_ID:
            raise SyntheticExecutionNotAuthorized("SYNTHETIC_EXECUTION_NOT_AUTHORIZED")
        if self.lifecycle != LIFECYCLE_AUTHORIZED_UNUSED:
            raise SyntheticExecutionNotAuthorized("SYNTHETIC_EXECUTION_NOT_AUTHORIZED")


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _run_git(repo_root: Path, *args: str) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        ["git", "-C", str(repo_root), *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def _require_git_ok(proc: subprocess.CompletedProcess[bytes], what: str) -> bytes:
    if proc.returncode != 0:
        raise SyntheticExecutionNotAuthorized(
            f"SYNTHETIC_EXECUTION_NOT_AUTHORIZED: git {what} failed"
        )
    return proc.stdout


def _head_sha(repo_root: Path) -> str:
    proc = _run_git(repo_root, "rev-parse", "HEAD")
    return _require_git_ok(proc, "rev-parse HEAD").decode("ascii").strip().lower()


def _tree_sha(repo_root: Path) -> str:
    proc = _run_git(repo_root, "rev-parse", "HEAD^{tree}")
    return _require_git_ok(proc, "rev-parse HEAD^{tree}").decode("ascii").strip().lower()


def _is_ancestor(repo_root: Path, ancestor: str, descendant: str) -> bool:
    proc = _run_git(repo_root, "merge-base", "--is-ancestor", ancestor, descendant)
    return proc.returncode == 0


def _commit_tree(repo_root: Path, commit: str) -> str:
    proc = _run_git(repo_root, "rev-parse", f"{commit}^{{tree}}")
    return _require_git_ok(proc, "rev-parse commit tree").decode("ascii").strip().lower()


def _head_blob(repo_root: Path, git_path: str) -> bytes | None:
    if git_path.startswith("/") or ".." in Path(git_path).parts:
        raise SyntheticExecutionNotAuthorized("SYNTHETIC_EXECUTION_NOT_AUTHORIZED")
    proc = _run_git(repo_root, "cat-file", "-e", f"HEAD:{git_path}")
    if proc.returncode != 0:
        return None
    proc = _run_git(repo_root, "cat-file", "blob", f"HEAD:{git_path}")
    return _require_git_ok(proc, f"cat-file HEAD:{git_path}")


def _commit_blob(repo_root: Path, commit: str, git_path: str) -> bytes:
    if git_path.startswith("/") or ".." in Path(git_path).parts:
        raise SyntheticExecutionNotAuthorized("SYNTHETIC_EXECUTION_NOT_AUTHORIZED")
    proc = _run_git(repo_root, "cat-file", "blob", f"{commit}:{git_path}")
    return _require_git_ok(proc, f"cat-file {commit}:{git_path}")


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _refuse(detail: str) -> None:
    raise SyntheticExecutionNotAuthorized(
        f"SYNTHETIC_EXECUTION_NOT_AUTHORIZED: {detail}"
    )


def describe_authorization_state() -> dict[str, Any]:
    """Read-only lifecycle description. Never authorizes execution."""
    root = _repo_root()
    try:
        blob = _head_blob(root, CANONICAL_AUTHORIZATION_PATH)
        claim = _head_blob(root, CANONICAL_CLAIM_PATH)
        if blob is None:
            lifecycle = LIFECYCLE_NOT_AUTHORIZED
        elif claim is not None:
            lifecycle = LIFECYCLE_CONSUMED
        else:
            payload = json.loads(blob.decode("utf-8"))
            if payload.get("authorization_consumed") is True:
                lifecycle = LIFECYCLE_CONSUMED
            elif (
                payload.get("status") == "AUTHORIZED_FOR_ONE_PRODUCTION_EXECUTION"
                and payload.get("synthetic_execution_authorized") is True
                and payload.get("production_calibration_executed") is False
                and payload.get("authorization_consumed") is False
            ):
                lifecycle = LIFECYCLE_AUTHORIZED_UNUSED
            else:
                lifecycle = LIFECYCLE_NOT_AUTHORIZED
        return {
            "lifecycle": lifecycle,
            "canonical_path": CANONICAL_AUTHORIZATION_PATH,
            "synthetic_execution_authorized": lifecycle == LIFECYCLE_AUTHORIZED_UNUSED,
            "production_calibration_executed": False,
            "authorization_consumed": lifecycle == LIFECYCLE_CONSUMED,
            "real_data_path": False,
        }
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, TypeError):
        return {
            "lifecycle": LIFECYCLE_NOT_AUTHORIZED,
            "canonical_path": CANONICAL_AUTHORIZATION_PATH,
            "synthetic_execution_authorized": False,
            "production_calibration_executed": False,
            "authorization_consumed": False,
            "real_data_path": False,
        }


def _expected_grid() -> dict[str, Any]:
    prereg = load_frozen_prereg()
    live = frozen_production_authority()
    scenario_ids = [item["id"] for item in prereg["scenarios"]]
    return {
        "planned_worlds": int(live["planned_total_worlds"]),
        "worlds_per_cell": int(live["worlds_per_primary_scenario"]),
        "scenario_ids": scenario_ids,
        "root_seed": int(live["root_seed"]),
        "primary_n_rows": int(live["primary_N"]),
        "small_sensitivity_n": list(live["small_sensitivity_N"]),
        "bootstrap_replicates": int(live["bootstrap_replicates"]),
        "placebo_replicates": int(live["placebo_replicates"]),
        "visibility_replicates": int(live["visibility_replicates"]),
        "block_rows": int(live["block_rows"]),
    }


def _grids_equal(left: Mapping[str, Any], right: Mapping[str, Any]) -> bool:
    return (
        int(left["planned_worlds"]) == int(right["planned_worlds"]) == PRODUCTION_PLANNED_TOTAL_WORLDS
        and int(left["worlds_per_cell"]) == int(right["worlds_per_cell"]) == PRODUCTION_WORLDS_PER_CELL
        and list(left["scenario_ids"]) == list(right["scenario_ids"])
        and int(left["root_seed"]) == int(right["root_seed"]) == ROOT_SEED
        and int(left["primary_n_rows"]) == int(right["primary_n_rows"]) == PRODUCTION_PRIMARY_N
        and [int(x) for x in left["small_sensitivity_n"]]
        == [int(x) for x in right["small_sensitivity_n"]]
        == list(PRODUCTION_SMALL_N)
        and int(left["bootstrap_replicates"])
        == int(right["bootstrap_replicates"])
        == PRODUCTION_BOOTSTRAP_REPLICATES
        and int(left["placebo_replicates"])
        == int(right["placebo_replicates"])
        == PRODUCTION_PLACEBO_REPLICATES
        and int(left["visibility_replicates"])
        == int(right["visibility_replicates"])
        == PRODUCTION_VISIBILITY_REPLICATES
        and int(left["block_rows"]) == int(right["block_rows"]) == PRODUCTION_BLOCK_ROWS
    )


def verify_tracked_one_shot_authorization() -> VerifiedProductionAuthorization:
    """Mint a production proof from canonical HEAD blobs only."""
    root = _repo_root()
    head = _head_sha(root)
    tree = _tree_sha(root)
    blob = _head_blob(root, CANONICAL_AUTHORIZATION_PATH)
    if blob is None:
        _refuse("authorization artifact absent from HEAD")
    try:
        payload = json.loads(blob.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SyntheticExecutionNotAuthorized(
            "SYNTHETIC_EXECUTION_NOT_AUTHORIZED: malformed authorization"
        ) from exc
    if not isinstance(payload, dict):
        _refuse("malformed authorization")
    if payload.get("unit_id") != UNIT_ID:
        _refuse("wrong unit_id")
    if payload.get("authorization_id") != AUTHORIZATION_ID:
        _refuse("wrong authorization_id")
    if payload.get("schema_version") != "1.0":
        _refuse("unsupported authorization schema")
    if payload.get("status") != "AUTHORIZED_FOR_ONE_PRODUCTION_EXECUTION":
        _refuse("authorization status is not one-shot production")
    if payload.get("lifecycle") != LIFECYCLE_AUTHORIZED_UNUSED:
        _refuse("authorization lifecycle is not AUTHORIZED_UNUSED")
    if payload.get("authorized_run_count") != 1:
        _refuse("authorized_run_count must be 1")
    if payload.get("synthetic_execution_authorized") is not True:
        _refuse("synthetic_execution_authorized is not true")
    if payload.get("production_calibration_executed") is not False:
        _refuse("production_calibration_executed must be false on unused authorization")
    if payload.get("authorization_consumed") is not False:
        _refuse("authorization_consumed must be false on unused authorization")
    for name in _FALSE_BOUNDARIES:
        if payload.get(name) is not False:
            _refuse(f"{name} must remain false")

    prereg = payload.get("frozen_prereg_identity")
    if not isinstance(prereg, dict):
        _refuse("missing frozen_prereg_identity")
    if prereg.get("json_path") != "docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1_PREREG.json":
        _refuse("canonical prereg json path mismatch")
    if prereg.get("md_path") != "docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1_PREREG.md":
        _refuse("canonical prereg md path mismatch")
    json_blob = _head_blob(root, prereg["json_path"])
    md_blob = _head_blob(root, prereg["md_path"])
    if json_blob is None or md_blob is None:
        _refuse("frozen prereg missing from HEAD")
    if _sha256_bytes(json_blob) != prereg.get("json_sha256"):
        _refuse("wrong prereg json identity")
    if _sha256_bytes(md_blob) != prereg.get("md_sha256"):
        _refuse("wrong prereg md identity")

    impl = payload.get("frozen_implementation_identity")
    if not isinstance(impl, dict):
        _refuse("missing frozen_implementation_identity")
    reviewed = str(impl.get("reviewed_implementation_commit", "")).lower()
    reviewed_tree = str(impl.get("reviewed_implementation_tree", "")).lower()
    freeze = str(impl.get("implementation_freeze_commit", "")).lower()
    merge = str(impl.get("main_merge_commit", "")).lower()
    if len(reviewed) != 40 or len(freeze) != 40 or len(merge) != 40:
        _refuse("implementation identity commits must be 40-hex SHAs")
    if not _is_ancestor(root, reviewed, head):
        _refuse("wrong implementation identity: reviewed commit is not an ancestor of HEAD")
    if not _is_ancestor(root, freeze, head):
        _refuse("wrong implementation identity: freeze commit is not an ancestor of HEAD")
    if not _is_ancestor(root, merge, head):
        _refuse("wrong implementation identity: main merge commit is not an ancestor of HEAD")
    if _commit_tree(root, reviewed) != reviewed_tree:
        _refuse("wrong implementation identity: reviewed tree mismatch")
    lib_path = impl.get("lib_path")
    if lib_path != "scripts/research/harness_synthetic_edge_calibration_v1_lib.py":
        _refuse("canonical implementation lib path mismatch")
    lib_bytes = _commit_blob(root, reviewed, lib_path)
    if _sha256_bytes(lib_bytes) != impl.get("lib_sha256_at_reviewed_implementation_commit"):
        _refuse("wrong implementation identity: reviewed lib bytes")

    grid = payload.get("authorized_grid")
    if not isinstance(grid, dict):
        _refuse("missing authorized_grid")
    expected = _expected_grid()
    if not _grids_equal(grid, expected):
        _refuse("modified production grid")

    claim = _head_blob(root, CANONICAL_CLAIM_PATH)
    if claim is not None:
        raise AuthorizationConsumed("SYNTHETIC_EXECUTION_NOT_AUTHORIZED: authorization consumed")
    consumption = payload.get("consumption")
    if isinstance(consumption, dict):
        claim_path = consumption.get("durable_claim_path")
        if claim_path and claim_path != CANONICAL_CLAIM_PATH:
            _refuse("consumption claim path is not canonical")

    return VerifiedProductionAuthorization(
        authorization_id=AUTHORIZATION_ID,
        authorization_blob_sha256=_sha256_bytes(blob),
        head_sha=head,
        tree_sha=tree,
        unit_id=UNIT_ID,
        grid=dict(expected),
        lifecycle=LIFECYCLE_AUTHORIZED_UNUSED,
        _mint=_MINT,
    )


def production_world_plan(proof: VerifiedProductionAuthorization) -> tuple[tuple[str, int, int], ...]:
    """Deterministic 3200-world identity plan. Does not simulate outcomes."""
    proof.assert_minted()
    grid = proof.grid
    jobs: list[tuple[str, int, int]] = []
    worlds = int(grid["worlds_per_cell"])
    primary_n = int(grid["primary_n_rows"])
    for scenario_id in grid["scenario_ids"]:
        for world_index in range(worlds):
            jobs.append((str(scenario_id), primary_n, world_index))
    small_ns = [int(n) for n in grid["small_sensitivity_n"]]
    for extra_n in small_ns:
        for world_index in range(worlds):
            jobs.append(("SMALL", extra_n, world_index))
    if len(jobs) != PRODUCTION_PLANNED_TOTAL_WORLDS:
        _refuse("production world plan is not 3200 identities")
    return tuple(jobs)


def _production_monte_carlo_seam(proof: VerifiedProductionAuthorization) -> dict[str, Any]:
    """Unique gated hook immediately before expensive Monte Carlo execution.

    This authorization PR does not arm or invoke the 3200-world loop.
    """
    proof.assert_minted()
    raise AuthorizedExecutionBoundaryReached(proof)


def run_authorized_production_grid(*args: Any, **kwargs: Any) -> dict[str, Any]:
    if args or kwargs:
        raise SyntheticExecutionNotAuthorized(
            "SYNTHETIC_EXECUTION_NOT_AUTHORIZED: caller arguments cannot authorize execution"
        )
    proof = verify_tracked_one_shot_authorization()
    plan = production_world_plan(proof)
    if len(plan) != PRODUCTION_PLANNED_TOTAL_WORLDS:
        _refuse("production world plan drifted")
    if len(FEATURE_IDS) != 10:
        _refuse("candidate library drifted")
    return _production_monte_carlo_seam(proof)
