"""Tracked one-shot production authorization for HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1.

Authority is repository state plus the bytes actually executed from this
checkout. Caller kwargs, environment variables, alternate paths, minted proof
objects, and historical ancestry alone cannot authorize execution.

Production scientific authority is re-derived from frozen module constants and
the tracked prereg at the production boundary. A proof object is diagnostic
only and cannot define the grid.

This module does not run the 3200-world Monte Carlo. After a clean executed-byte
verification and an atomic one-shot reservation, the unique production seam is
reached and then stops without generating a RESULT.
"""

from __future__ import annotations

import hashlib
import json
import os
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
from scripts.research.lib.research_harness import CodeIdentityError, verify_git_freeze

CANONICAL_AUTHORIZATION_PATH = (
    "docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1_EXECUTION_AUTHORIZATION.json"
)
CANONICAL_CLAIM_PATH = (
    "docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1_PRODUCTION_EXECUTION_CLAIM.json"
)
CANONICAL_RESERVATION_PATH = (
    "docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1_PRODUCTION_RESERVATION.json"
)
AUTHORIZATION_ID = (
    "HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1_ONE_SHOT_PRODUCTION_EXECUTION_V1"
)
LIB_REL = "scripts/research/harness_synthetic_edge_calibration_v1_lib.py"
RUNNER_REL = "scripts/research/harness_synthetic_edge_calibration_v1.py"
AUTH_REL = "scripts/research/harness_synthetic_edge_calibration_v1_auth.py"
PRODUCTION_REL = "scripts/research/harness_synthetic_edge_calibration_v1_production.py"
EXECUTION_AUTHORITY_PATHS = (LIB_REL, RUNNER_REL, AUTH_REL)
FROZEN_REVIEWED_LIB_SHA256 = (
    "12230dcad714e3a06d3f57de69b78fedcab088be950af3d06f959366f01d6c51"
)
LIFECYCLE_NOT_AUTHORIZED = "NOT_AUTHORIZED"
LIFECYCLE_AUTHORIZED_UNUSED = "AUTHORIZED_UNUSED"
LIFECYCLE_RESERVED = "RESERVED"
LIFECYCLE_EXECUTED_CONSUMED = "EXECUTED_CONSUMED"
LIFECYCLE_FAILED_CONSUMED = "FAILED_CONSUMED"
LIFECYCLE_CONSUMED = LIFECYCLE_EXECUTED_CONSUMED
_MINT = object()
_FALSE_BOUNDARIES = (
    "real_market_data_access_authorized",
    "b2_06_scientific_execution_authorized",
    "validation_2025_authorized",
    "oos_2026_authorized",
)
_FROZEN_GRID_LITERALS = {
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
_CONSUMED_LIFECYCLES = frozenset(
    {
        LIFECYCLE_RESERVED,
        LIFECYCLE_EXECUTED_CONSUMED,
        LIFECYCLE_FAILED_CONSUMED,
        LIFECYCLE_CONSUMED,
    }
)


class AuthorizationConsumed(SyntheticExecutionNotAuthorized):
    """The one-shot authorization is reserved or consumed and is not reusable."""


class AuthorizedExecutionBoundaryReached(RuntimeError):
    """Reservation obtained; Monte Carlo remains unarmed in this stage."""

    def __init__(self, diagnostics: "ProductionBoundaryDiagnostics") -> None:
        self.diagnostics = diagnostics
        super().__init__("AUTHORIZED_PRODUCTION_EXECUTION_BOUNDARY")

    @property
    def proof(self) -> None:
        """Captured proofs are not exposed as reusable authority objects."""
        return None


@dataclass(frozen=True)
class ProductionBoundaryDiagnostics:
    """Non-authoritative identity of a reserved, unarmed production boundary."""

    authorization_id: str
    authorization_blob_sha256: str
    head_sha: str
    tree_sha: str
    reservation_sha256: str
    reservation_lifecycle: str
    run_identity: str
    monte_carlo_invoked: bool = False


@dataclass(frozen=True)
class VerifiedProductionAuthorization:
    """Diagnostic record that verification occurred.

    This is not a capability. ``_MINT`` is not a security boundary. Executors
    must re-derive scientific authority from frozen/tracked sources.
    """

    authorization_id: str
    authorization_blob_sha256: str
    head_sha: str
    tree_sha: str
    unit_id: str
    grid: dict[str, Any]
    lifecycle: str
    execution_authority: dict[str, str] = field(default_factory=dict)
    _mint: object = field(default=None, repr=False, compare=False)

    def assert_minted(self) -> None:
        raise SyntheticExecutionNotAuthorized(
            "SYNTHETIC_EXECUTION_NOT_AUTHORIZED: proof objects cannot authorize execution"
        )


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _executing_authority_file(rel: str) -> Path:
    if rel == LIB_REL:
        from scripts.research import harness_synthetic_edge_calibration_v1_lib as lib_mod

        return Path(lib_mod.__file__).resolve()
    if rel == RUNNER_REL:
        return Path(__file__).resolve().with_name(Path(rel).name)
    if rel == AUTH_REL:
        return Path(__file__).resolve()
    raise SyntheticExecutionNotAuthorized("SYNTHETIC_EXECUTION_NOT_AUTHORIZED")


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


def _canonical_json_bytes(payload: Mapping[str, Any]) -> bytes:
    return (json.dumps(payload, sort_keys=True, indent=2, ensure_ascii=False) + "\n").encode(
        "utf-8"
    )


def _refuse(detail: str) -> None:
    raise SyntheticExecutionNotAuthorized(
        f"SYNTHETIC_EXECUTION_NOT_AUTHORIZED: {detail}"
    )


def _worktree_regular_file(repo_root: Path, rel: str) -> Path | None:
    path = repo_root / rel
    if path.exists() or path.is_symlink():
        return path
    return None


def _lifecycle_from_reservation_bytes(raw: bytes) -> str:
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError):
        return LIFECYCLE_FAILED_CONSUMED
    if not isinstance(payload, dict):
        return LIFECYCLE_FAILED_CONSUMED
    lifecycle = payload.get("lifecycle")
    if lifecycle in _CONSUMED_LIFECYCLES:
        return str(lifecycle)
    return LIFECYCLE_FAILED_CONSUMED


def _existing_consumption_lifecycle(repo_root: Path) -> str | None:
    claim_path = _worktree_regular_file(repo_root, CANONICAL_CLAIM_PATH)
    if claim_path is not None:
        return LIFECYCLE_EXECUTED_CONSUMED
    if _head_blob(repo_root, CANONICAL_CLAIM_PATH) is not None:
        return LIFECYCLE_EXECUTED_CONSUMED
    reservation_path = _worktree_regular_file(repo_root, CANONICAL_RESERVATION_PATH)
    if reservation_path is not None:
        try:
            raw = reservation_path.read_bytes()
        except OSError:
            return LIFECYCLE_FAILED_CONSUMED
        return _lifecycle_from_reservation_bytes(raw)
    head_reservation = _head_blob(repo_root, CANONICAL_RESERVATION_PATH)
    if head_reservation is not None:
        return _lifecycle_from_reservation_bytes(head_reservation)
    return None


def describe_authorization_state() -> dict[str, Any]:
    """Read-only lifecycle description. Never authorizes execution."""
    root = _repo_root()
    try:
        consumed = _existing_consumption_lifecycle(root)
        blob = _head_blob(root, CANONICAL_AUTHORIZATION_PATH)
        if consumed is not None:
            lifecycle = consumed
        elif blob is None:
            lifecycle = LIFECYCLE_NOT_AUTHORIZED
        else:
            payload = json.loads(blob.decode("utf-8"))
            if payload.get("authorization_consumed") is True:
                lifecycle = LIFECYCLE_EXECUTED_CONSUMED
            elif (
                payload.get("status") == "AUTHORIZED_FOR_ONE_PRODUCTION_EXECUTION"
                and payload.get("synthetic_execution_authorized") is True
                and payload.get("production_calibration_executed") is False
                and payload.get("authorization_consumed") is False
                and payload.get("lifecycle") == LIFECYCLE_AUTHORIZED_UNUSED
            ):
                lifecycle = LIFECYCLE_AUTHORIZED_UNUSED
            else:
                lifecycle = LIFECYCLE_NOT_AUTHORIZED
        consumed_now = lifecycle in _CONSUMED_LIFECYCLES
        return {
            "lifecycle": lifecycle,
            "canonical_path": CANONICAL_AUTHORIZATION_PATH,
            "reservation_path": CANONICAL_RESERVATION_PATH,
            "synthetic_execution_authorized": lifecycle == LIFECYCLE_AUTHORIZED_UNUSED,
            "production_calibration_executed": False,
            "authorization_consumed": consumed_now,
            "real_data_path": False,
        }
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, TypeError):
        return {
            "lifecycle": LIFECYCLE_NOT_AUTHORIZED,
            "canonical_path": CANONICAL_AUTHORIZATION_PATH,
            "reservation_path": CANONICAL_RESERVATION_PATH,
            "synthetic_execution_authorized": False,
            "production_calibration_executed": False,
            "authorization_consumed": False,
            "real_data_path": False,
        }


def _literal_grid() -> dict[str, Any]:
    return {
        "planned_worlds": int(_FROZEN_GRID_LITERALS["planned_worlds"]),
        "worlds_per_cell": int(_FROZEN_GRID_LITERALS["worlds_per_cell"]),
        "scenario_ids": list(_FROZEN_GRID_LITERALS["scenario_ids"]),
        "root_seed": int(_FROZEN_GRID_LITERALS["root_seed"]),
        "primary_n_rows": int(_FROZEN_GRID_LITERALS["primary_n_rows"]),
        "small_sensitivity_n": list(_FROZEN_GRID_LITERALS["small_sensitivity_n"]),
        "bootstrap_replicates": int(_FROZEN_GRID_LITERALS["bootstrap_replicates"]),
        "placebo_replicates": int(_FROZEN_GRID_LITERALS["placebo_replicates"]),
        "visibility_replicates": int(_FROZEN_GRID_LITERALS["visibility_replicates"]),
        "block_rows": int(_FROZEN_GRID_LITERALS["block_rows"]),
    }


def _expected_grid() -> dict[str, Any]:
    prereg = load_frozen_prereg()
    live = frozen_production_authority()
    scenario_ids = [item["id"] for item in prereg["scenarios"]]
    derived = {
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
    _require_frozen_grid(derived)
    return derived


def _grids_equal(left: Mapping[str, Any], right: Mapping[str, Any]) -> bool:
    try:
        return (
            int(left["planned_worlds"])
            == int(right["planned_worlds"])
            == PRODUCTION_PLANNED_TOTAL_WORLDS
            == int(_FROZEN_GRID_LITERALS["planned_worlds"])
            and int(left["worlds_per_cell"])
            == int(right["worlds_per_cell"])
            == PRODUCTION_WORLDS_PER_CELL
            == int(_FROZEN_GRID_LITERALS["worlds_per_cell"])
            and list(left["scenario_ids"])
            == list(right["scenario_ids"])
            == list(_FROZEN_GRID_LITERALS["scenario_ids"])
            and int(left["root_seed"])
            == int(right["root_seed"])
            == ROOT_SEED
            == int(_FROZEN_GRID_LITERALS["root_seed"])
            and int(left["primary_n_rows"])
            == int(right["primary_n_rows"])
            == PRODUCTION_PRIMARY_N
            == int(_FROZEN_GRID_LITERALS["primary_n_rows"])
            and [int(x) for x in left["small_sensitivity_n"]]
            == [int(x) for x in right["small_sensitivity_n"]]
            == list(PRODUCTION_SMALL_N)
            == list(_FROZEN_GRID_LITERALS["small_sensitivity_n"])
            and int(left["bootstrap_replicates"])
            == int(right["bootstrap_replicates"])
            == PRODUCTION_BOOTSTRAP_REPLICATES
            == int(_FROZEN_GRID_LITERALS["bootstrap_replicates"])
            and int(left["placebo_replicates"])
            == int(right["placebo_replicates"])
            == PRODUCTION_PLACEBO_REPLICATES
            == int(_FROZEN_GRID_LITERALS["placebo_replicates"])
            and int(left["visibility_replicates"])
            == int(right["visibility_replicates"])
            == PRODUCTION_VISIBILITY_REPLICATES
            == int(_FROZEN_GRID_LITERALS["visibility_replicates"])
            and int(left["block_rows"])
            == int(right["block_rows"])
            == PRODUCTION_BLOCK_ROWS
            == int(_FROZEN_GRID_LITERALS["block_rows"])
        )
    except (KeyError, TypeError, ValueError):
        return False


def _require_frozen_grid(grid: Mapping[str, Any]) -> dict[str, Any]:
    expected = _literal_grid()
    if not _grids_equal(grid, expected):
        _refuse("production grid is not the frozen authority")
    return expected


def _require_clean_executed_checkout(repo_root: Path, head: str) -> None:
    try:
        freeze = verify_git_freeze(repo_root, head)
    except CodeIdentityError as exc:
        raise SyntheticExecutionNotAuthorized(
            f"SYNTHETIC_EXECUTION_NOT_AUTHORIZED: executed checkout is not a clean verified freeze ({exc})"
        ) from exc
    tree = _tree_sha(repo_root)
    if freeze.code_sha != head or freeze.tree_oid != tree:
        _refuse("verified freeze identity drifted from HEAD")


def _bind_execution_authority(repo_root: Path, payload: Mapping[str, Any]) -> dict[str, str]:
    exec_auth = payload.get("execution_authority")
    if not isinstance(exec_auth, dict):
        _refuse("missing execution_authority")
    paths = exec_auth.get("paths")
    if list(paths or []) != list(EXECUTION_AUTHORITY_PATHS):
        _refuse("execution_authority paths are not canonical")
    impl = payload.get("frozen_implementation_identity")
    if not isinstance(impl, dict):
        _refuse("missing frozen_implementation_identity")
    reviewed = str(impl.get("reviewed_implementation_commit", "")).lower()
    bound: dict[str, str] = {}
    for rel, json_key in (
        (LIB_REL, "lib_sha256"),
        (RUNNER_REL, "runner_sha256"),
        (AUTH_REL, "auth_sha256"),
    ):
        head_bytes = _head_blob(repo_root, rel)
        if head_bytes is None:
            _refuse(f"execution authority missing from HEAD: {rel}")
        worktree = repo_root / rel
        if worktree.is_symlink() or not worktree.is_file():
            _refuse(f"execution authority worktree is not a regular file: {rel}")
        try:
            worktree_bytes = worktree.read_bytes()
            executing_bytes = _executing_authority_file(rel).read_bytes()
        except OSError as exc:
            raise SyntheticExecutionNotAuthorized(
                f"SYNTHETIC_EXECUTION_NOT_AUTHORIZED: unable to read executed bytes for {rel}"
            ) from exc
        if worktree_bytes != head_bytes:
            _refuse(f"worktree bytes differ from HEAD for {rel}")
        if executing_bytes != head_bytes:
            _refuse(f"executed bytes differ from HEAD for {rel}")
        digest = _sha256_bytes(head_bytes)
        if exec_auth.get(json_key) != digest:
            _refuse(f"HEAD {rel} does not match tracked execution_authority.{json_key}")
        if json_key == "lib_sha256":
            if digest != FROZEN_REVIEWED_LIB_SHA256:
                _refuse("HEAD scientific lib is not the frozen reviewed implementation")
            if digest != impl.get("lib_sha256_at_reviewed_implementation_commit"):
                _refuse("HEAD lib sha256 is not the reviewed implementation identity")
            if impl.get("lib_path") != LIB_REL:
                _refuse("canonical implementation lib path mismatch")
            reviewed_bytes = _commit_blob(repo_root, reviewed, LIB_REL)
            if _sha256_bytes(reviewed_bytes) != digest:
                _refuse("HEAD scientific lib differs from frozen reviewed implementation commit")
        bound[json_key] = digest
        bound[rel] = digest
    return bound


def _atomic_create_exclusive(path: Path, data: bytes) -> None:
    if path.is_symlink() or path.parent.is_symlink():
        _refuse("refusing to write reservation through a symlink")
    path.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(path, flags, 0o644)
    except FileExistsError as exc:
        raise AuthorizationConsumed(
            "SYNTHETIC_EXECUTION_NOT_AUTHORIZED: authorization already reserved"
        ) from exc
    except OSError as exc:
        raise SyntheticExecutionNotAuthorized(
            f"SYNTHETIC_EXECUTION_NOT_AUTHORIZED: unable to create exclusive reservation ({exc})"
        ) from exc
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
    except Exception:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass
        raise
    persisted = path.read_bytes()
    if persisted != data:
        _refuse("written reservation bytes differ from intended reservation")


def _reservation_payload(
    *,
    authorization_blob_sha256: str,
    head_sha: str,
    tree_sha: str,
    execution_authority: Mapping[str, str],
    prereg_json_sha256: str,
    prereg_md_sha256: str,
    grid: Mapping[str, Any],
    lifecycle: str,
) -> dict[str, Any]:
    body = {
        "schema_version": "1.0",
        "unit_id": UNIT_ID,
        "authorization_id": AUTHORIZATION_ID,
        "lifecycle": lifecycle,
        "authorization_blob_sha256": authorization_blob_sha256,
        "authorization_path": CANONICAL_AUTHORIZATION_PATH,
        "reservation_path": CANONICAL_RESERVATION_PATH,
        "claim_path": CANONICAL_CLAIM_PATH,
        "head_sha": head_sha,
        "tree_sha": tree_sha,
        "execution_authority": {
            "paths": list(EXECUTION_AUTHORITY_PATHS),
            "lib_sha256": execution_authority["lib_sha256"],
            "runner_sha256": execution_authority["runner_sha256"],
            "auth_sha256": execution_authority["auth_sha256"],
        },
        "prereg": {
            "json_path": "docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1_PREREG.json",
            "md_path": "docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1_PREREG.md",
            "json_sha256": prereg_json_sha256,
            "md_sha256": prereg_md_sha256,
        },
        "grid": dict(grid),
        "monte_carlo_invoked": False,
        "production_calibration_executed": False,
        "automatic_retry_authorized": False,
    }
    body["run_identity"] = _sha256_bytes(_canonical_json_bytes(body))
    return body


def _mark_reservation_lifecycle(path: Path, payload: dict[str, Any], lifecycle: str) -> None:
    updated = dict(payload)
    updated["lifecycle"] = lifecycle
    data = _canonical_json_bytes(updated)
    path.write_bytes(data)


def _acquire_one_shot_reservation(
    repo_root: Path,
    *,
    authorization_blob_sha256: str,
    head_sha: str,
    tree_sha: str,
    execution_authority: Mapping[str, str],
    prereg_json_sha256: str,
    prereg_md_sha256: str,
    grid: Mapping[str, Any],
) -> dict[str, Any]:
    existing = _existing_consumption_lifecycle(repo_root)
    if existing is not None:
        raise AuthorizationConsumed(
            f"SYNTHETIC_EXECUTION_NOT_AUTHORIZED: authorization consumed ({existing})"
        )
    payload = _reservation_payload(
        authorization_blob_sha256=authorization_blob_sha256,
        head_sha=head_sha,
        tree_sha=tree_sha,
        execution_authority=execution_authority,
        prereg_json_sha256=prereg_json_sha256,
        prereg_md_sha256=prereg_md_sha256,
        grid=grid,
        lifecycle=LIFECYCLE_RESERVED,
    )
    expected_auth = authorization_blob_sha256
    if payload["authorization_blob_sha256"] != expected_auth:
        _refuse("reservation is not bound to the tracked authorization")
    _require_frozen_grid(payload["grid"])
    path = repo_root / CANONICAL_RESERVATION_PATH
    _atomic_create_exclusive(path, _canonical_json_bytes(payload))
    persisted = json.loads(path.read_text(encoding="utf-8"))
    if persisted.get("authorization_blob_sha256") != expected_auth:
        _mark_reservation_lifecycle(path, persisted, LIFECYCLE_FAILED_CONSUMED)
        _refuse("reservation bound to wrong authorization")
    if persisted.get("reservation_path") != CANONICAL_RESERVATION_PATH:
        _mark_reservation_lifecycle(path, persisted, LIFECYCLE_FAILED_CONSUMED)
        _refuse("reservation path substitution")
    if persisted.get("claim_path") != CANONICAL_CLAIM_PATH:
        _mark_reservation_lifecycle(path, persisted, LIFECYCLE_FAILED_CONSUMED)
        _refuse("claim path substitution")
    return persisted


def verify_tracked_one_shot_authorization() -> VerifiedProductionAuthorization:
    """Verify Git/byte authority. This is not a reusable execution capability."""
    root = _repo_root()
    consumed = _existing_consumption_lifecycle(root)
    if consumed is not None:
        raise AuthorizationConsumed(
            f"SYNTHETIC_EXECUTION_NOT_AUTHORIZED: authorization consumed ({consumed})"
        )
    head = _head_sha(root)
    tree = _tree_sha(root)
    _require_clean_executed_checkout(root, head)
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
    executing_prereg_json = Path(__file__).resolve().parents[2] / prereg["json_path"]
    executing_prereg_md = Path(__file__).resolve().parents[2] / prereg["md_path"]
    if executing_prereg_json.read_bytes() != json_blob or executing_prereg_md.read_bytes() != md_blob:
        _refuse("executed prereg bytes differ from HEAD")

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

    execution_authority = _bind_execution_authority(root, payload)

    grid = payload.get("authorized_grid")
    if not isinstance(grid, dict):
        _refuse("missing authorized_grid")
    expected = _expected_grid()
    if not _grids_equal(grid, expected):
        _refuse("modified production grid")

    consumption = payload.get("consumption")
    if isinstance(consumption, dict):
        claim_path = consumption.get("durable_claim_path")
        if claim_path and claim_path != CANONICAL_CLAIM_PATH:
            _refuse("consumption claim path is not canonical")
        reservation_path = consumption.get("durable_reservation_path")
        if reservation_path and reservation_path != CANONICAL_RESERVATION_PATH:
            _refuse("consumption reservation path is not canonical")

    return VerifiedProductionAuthorization(
        authorization_id=AUTHORIZATION_ID,
        authorization_blob_sha256=_sha256_bytes(blob),
        head_sha=head,
        tree_sha=tree,
        unit_id=UNIT_ID,
        grid=dict(expected),
        lifecycle=LIFECYCLE_AUTHORIZED_UNUSED,
        execution_authority=dict(execution_authority),
        _mint=_MINT,
    )


def production_world_plan(*args: Any, **kwargs: Any) -> tuple[tuple[str, int, int], ...]:
    """Deterministic 3200-world identity plan from frozen authority only."""
    if args or kwargs:
        raise SyntheticExecutionNotAuthorized(
            "SYNTHETIC_EXECUTION_NOT_AUTHORIZED: caller arguments cannot authorize the production plan"
        )
    grid = _expected_grid()
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
    if jobs[0] != ("NULL", 5000, 0) or jobs[-1] != ("SMALL", 10000, 399):
        _refuse("production world plan identity order drifted")
    return tuple(jobs)


def _production_monte_carlo_seam(reservation: Mapping[str, Any]) -> dict[str, Any]:
    """Unique gated hook immediately before expensive Monte Carlo execution.

    This authorization PR does not arm or invoke the 3200-world loop.
    """
    _require_frozen_grid(reservation["grid"])
    _require_frozen_grid(_expected_grid())
    plan = production_world_plan()
    if len(plan) != PRODUCTION_PLANNED_TOTAL_WORLDS:
        _refuse("production world plan drifted")
    raise AuthorizedExecutionBoundaryReached(
        ProductionBoundaryDiagnostics(
            authorization_id=AUTHORIZATION_ID,
            authorization_blob_sha256=str(reservation["authorization_blob_sha256"]),
            head_sha=str(reservation["head_sha"]),
            tree_sha=str(reservation["tree_sha"]),
            reservation_sha256=_sha256_bytes(_canonical_json_bytes(reservation)),
            reservation_lifecycle=str(reservation["lifecycle"]),
            run_identity=str(reservation["run_identity"]),
            monte_carlo_invoked=False,
        )
    )


def run_authorized_production_grid(*args: Any, **kwargs: Any) -> dict[str, Any]:
    if args or kwargs:
        raise SyntheticExecutionNotAuthorized(
            "SYNTHETIC_EXECUTION_NOT_AUTHORIZED: caller arguments cannot authorize execution"
        )
    root = _repo_root()
    if _head_blob(root, PRODUCTION_REL) is not None:
        _refuse(
            "HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1_PRODUCTION_DURABILITY supersedes "
            "#114 local reservation; production remains unarmed"
        )
    reservation: dict[str, Any] | None = None
    reservation_path = root / CANONICAL_RESERVATION_PATH
    try:
        diagnostic = verify_tracked_one_shot_authorization()
        grid = _expected_grid()
        _require_frozen_grid(grid)
        if diagnostic.grid and not _grids_equal(diagnostic.grid, grid):
            _refuse("diagnostic grid is not frozen authority")
        reservation = _acquire_one_shot_reservation(
            root,
            authorization_blob_sha256=diagnostic.authorization_blob_sha256,
            head_sha=diagnostic.head_sha,
            tree_sha=diagnostic.tree_sha,
            execution_authority=diagnostic.execution_authority,
            prereg_json_sha256=_sha256_bytes(
                _head_blob(root, "docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1_PREREG.json")
                or b""
            ),
            prereg_md_sha256=_sha256_bytes(
                _head_blob(root, "docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1_PREREG.md")
                or b""
            ),
            grid=grid,
        )
        if len(FEATURE_IDS) != 10:
            _refuse("candidate library drifted")
        return _production_monte_carlo_seam(reservation)
    except AuthorizedExecutionBoundaryReached:
        raise
    except Exception:
        if reservation is not None and reservation_path.is_file():
            try:
                _mark_reservation_lifecycle(
                    reservation_path, reservation, LIFECYCLE_FAILED_CONSUMED
                )
            except OSError:
                pass
        raise


def production_authorization_identity() -> dict[str, Any]:
    """Operator identity view. Does not authorize execution."""
    state = describe_authorization_state()
    authority = frozen_production_authority()
    return {
        "stage": "one_shot_synthetic_execution_authorization_repair",
        "unit_id": UNIT_ID,
        "implementation_exists": True,
        "implementation_frozen_before_production_execution": True,
        "production_calibration_executed": False,
        "synthetic_execution_authorized": bool(state["synthetic_execution_authorized"]),
        "authorization_consumed": bool(state["authorization_consumed"]),
        "authorization_lifecycle": state["lifecycle"],
        "real_market_data_access_authorized": False,
        "b2_06_scientific_execution_authorized": False,
        "validation_2025_authorized": False,
        "oos_2026_authorized": False,
        "production_bootstrap_replicates": authority["bootstrap_replicates"],
        "production_placebo_replicates": authority["placebo_replicates"],
        "production_visibility_replicates": authority["visibility_replicates"],
        "planned_total_worlds": authority["planned_total_worlds"],
        "real_data_path": False,
        "monte_carlo_armed": False,
        "execution_authority_paths": list(EXECUTION_AUTHORITY_PATHS),
        "reservation_path": CANONICAL_RESERVATION_PATH,
    }
