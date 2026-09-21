"""MARKET-06 one-shot canonical execution lifecycle.

Replaces the previous permanent-refusal architecture (red-team F-05) with
a *permit* architecture:

    IMPLEMENTATION_REPAIRED_AND_FROZEN
      -> RED_TEAM_PASS
      -> tracked ARM payload + ARM-bound implementation freeze
      -> tracked one-shot EXECUTION RESERVATION
      -> canonical execution (exactly once)
      -> deterministic RESULT persisted
      -> second canonical execution refused

No ARM, reservation, or result exists now, so canonical execution still
refuses. The point of this module is that a *future* tracked ARM can
authorize the EXACT same frozen scientific bytes with no edit to the
evaluator, parsers, bootstrap, or scientific runner logic.

Deliberately generic (red-team F-05/F-06 follow-up): this module does NOT
hardcode the repaired implementation-freeze commit, because that commit
cannot exist until after the commit that contains this file. The ARM names
its implementation freeze; this module authenticates whatever it names
against the live prereg freeze, the dataset identity, and the bytes now
executing.

All authority is read from immutable Git objects (red-team F-07). A file
present in the working tree never authorizes anything.

This module computes nothing scientific and reads no OHLC values.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from scripts.research import market_06_git_authority as gitauth
from scripts.research.market_06_git_authority import Market06GitAuthorityError

RESEARCH_ID = "MARKET-06_CROSS_VENUE_DISLOCATION_ADVERSE_PATH_RISK"

PREREG_FREEZE_HEAD = "e2d543eadb5425473b6d4b8d24c177c1d7ae7930"
PREREG_FREEZE_TREE = "a1706c775154fc65ad1d5eaaa5818f87b834a2b7"
PREREG_CONTENT_HEAD = "6342d24e6d872b6dbce91f9cdb8e7cfe689a6f59"
PREREG_CONTENT_TREE = "11658516cab22774501daa8e2e966c9a8861c9a3"

DATASET_ID = "MARKET_06_OKX_BINANCE_FEASIBILITY_V0"
SNAPSHOT_ID = "e0403e40a9b1e2903f15fb9283ec6caf54788e48153038982e364d4318183e68"
DURABLE_EVIDENCE_ROOT_SHA256 = (
    "f4b9e16a62707c70e782cc318399f3ba53ebb85c792e96cd12c164a98f0cdc6f"
)

AUTHORIZATION_KIND = "ONE_SHOT_CANONICAL_HISTORICAL_EXECUTION"

ARM_JSON_REL = "docs/research/MARKET_06_EXECUTION_ARM.json"
RESERVATION_JSON_REL = "docs/research/MARKET_06_EXECUTION_RESERVATION.json"
RESULT_JSON_REL = "docs/research/MARKET_06_CROSS_VENUE_DISLOCATION_RESULT.json"
RESULT_MD_REL = "docs/research/MARKET_06_CROSS_VENUE_DISLOCATION_RESULT.md"

EXECUTION_LOCK_REL = ".market_06_canonical_execution.lock"

# Scientific/lifecycle modules whose bytes are bound by the implementation
# freeze and re-verified at permit time. Changing any of them invalidates a
# previously issued ARM.
SCIENTIFIC_MODULE_RELPATHS: tuple[str, ...] = (
    "scripts/research/market_06_cross_venue_dislocation_authority.py",
    "scripts/research/market_06_cross_venue_dislocation_parsers.py",
    "scripts/research/market_06_cross_venue_dislocation_bootstrap.py",
    "scripts/research/market_06_cross_venue_dislocation_evaluator.py",
    "scripts/research/market_06_cross_venue_dislocation_runner.py",
    "scripts/research/market_06_year_stratified_circular_mbb.py",
    "scripts/research/market_06_canonical_reconstruction.py",
    "scripts/research/market_06_execution_lifecycle.py",
    "scripts/research/market_06_git_authority.py",
)

ARM_REQUIRED_FIELDS: tuple[str, ...] = (
    "research_id",
    "prereg_freeze_head",
    "prereg_freeze_tree",
    "implementation_freeze_head",
    "implementation_freeze_tree",
    "implementation_module_root",
    "dataset_id",
    "snapshot_id",
    "durable_evidence_root_sha256",
    "run_identity",
    "authorization_kind",
    "scientific_outcomes_inspected_before_arm",
    "protected_2025_opened",
    "protected_2026_opened",
)

# Fields a caller must never be able to supply; they are authority, not input.
FORBIDDEN_CALLER_KEYS = frozenset(
    {
        "authorize",
        "authorized",
        "force",
        "execute",
        "allow_real",
        "bypass",
        "execution_authorized",
        "arm",
        "arm_payload",
        "permit",
        "expected_sha256",
        "sha256",
        "prereg_head",
        "snapshot_id",
        "dataset_id",
        "run_identity",
        "implementation_freeze_head",
        "path",
        "paths",
        "source_path",
    }
)

BYPASS_ENV_KEYS = (
    "MARKET_06_EXECUTE",
    "MARKET_06_AUTHORIZATION",
    "MARKET_06_FORCE",
    "MARKET_06_ARM",
    "MARKET_06_PERMIT",
    "SIGNALBOT_MARKET_06_EXECUTE",
)

_PERMIT_TOKEN = object()


class Market06ExecutionNotAuthorized(RuntimeError):
    def __init__(self, message: str = "MARKET_06_EXECUTION_NOT_AUTHORIZED") -> None:
        super().__init__(message)


class Market06LifecycleError(RuntimeError):
    """Malformed or inconsistent tracked lifecycle artifact."""


@dataclass(frozen=True)
class ExecutionPermit:
    """Opaque authenticated permit. Only this module can mint one."""

    run_identity: str
    arm_commit: str
    implementation_freeze_head: str
    implementation_freeze_tree: str
    dataset_id: str
    snapshot_id: str
    durable_evidence_root_sha256: str
    authorization_kind: str
    _token: object = None

    def __post_init__(self) -> None:
        if self._token is not _PERMIT_TOKEN:
            raise Market06ExecutionNotAuthorized(
                "MARKET_06_PERMIT_CANNOT_BE_FORGED"
            )


def require_permit(permit: Any) -> ExecutionPermit:
    """Accept only a permit minted by this module."""

    if not isinstance(permit, ExecutionPermit):
        raise Market06ExecutionNotAuthorized("MARKET_06_PERMIT_REQUIRED")
    if getattr(permit, "_token", None) is not _PERMIT_TOKEN:
        raise Market06ExecutionNotAuthorized("MARKET_06_PERMIT_CANNOT_BE_FORGED")
    if permit.authorization_kind != AUTHORIZATION_KIND:
        raise Market06ExecutionNotAuthorized("MARKET_06_PERMIT_WRONG_KIND")
    return permit


def reject_caller_authority_override(args: tuple[Any, ...], kwargs: Mapping[str, Any]) -> None:
    if args:
        raise Market06ExecutionNotAuthorized(
            "positional arguments cannot redefine MARKET-06 authority"
        )
    hit = FORBIDDEN_CALLER_KEYS.intersection(kwargs)
    if hit:
        raise Market06ExecutionNotAuthorized(
            f"caller kwargs cannot redefine MARKET-06 authority:{sorted(hit)}"
        )


def env_bypass_attempted() -> bool:
    return any(os.environ.get(key) for key in BYPASS_ENV_KEYS)


def canonical_json_bytes(payload: Mapping[str, Any]) -> bytes:
    return (
        json.dumps(payload, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False)
        + "\n"
    ).encode("utf-8")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def live_module_sha256() -> dict[str, str]:
    """SHA-256 of the module bytes actually executing now.

    Authority is the frozen inventory; this is the value checked *against*
    it, so that mutated live bytes can never run under an old ARM.
    """

    root = gitauth.repo_root()
    out: dict[str, str] = {}
    for rel in SCIENTIFIC_MODULE_RELPATHS:
        path = root / rel
        if path.is_symlink() or not path.is_file():
            raise Market06LifecycleError(f"MARKET_06_MODULE_MISSING:{rel}")
        out[rel] = _sha256(path.read_bytes())
    return out


def run_identity_preimage(module_hashes: Mapping[str, str]) -> dict[str, Any]:
    """Content-only preimage. No commit SHAs, no clock, no uuid."""

    return {
        "schema": "market_06_run_identity",
        "schema_version": "1.0.0",
        "research_id": RESEARCH_ID,
        "prereg_content_head": PREREG_CONTENT_HEAD,
        "prereg_content_tree": PREREG_CONTENT_TREE,
        "dataset_id": DATASET_ID,
        "snapshot_id": SNAPSHOT_ID,
        "durable_evidence_root_sha256": DURABLE_EVIDENCE_ROOT_SHA256,
        "module_sha256": dict(sorted(module_hashes.items())),
        "authorization_kind": AUTHORIZATION_KIND,
    }


def derive_run_identity(module_hashes: Mapping[str, str] | None = None) -> str:
    hashes = dict(module_hashes) if module_hashes is not None else live_module_sha256()
    return _sha256(canonical_json_bytes(run_identity_preimage(hashes)))


def _load_tracked_json(commit: str, relpath: str, *, label: str) -> dict[str, Any]:
    try:
        raw = gitauth.cat_blob(commit, relpath)
    except Market06GitAuthorityError as exc:
        raise Market06ExecutionNotAuthorized(f"MARKET_06_{label}_NOT_TRACKED") from exc
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise Market06LifecycleError(f"MARKET_06_{label}_MALFORMED_JSON") from exc
    if not isinstance(payload, dict):
        raise Market06LifecycleError(f"MARKET_06_{label}_NOT_OBJECT")
    return payload


def verify_implementation_freeze(
    freeze_head: str,
    freeze_tree: str,
    freeze_relpath: str,
) -> dict[str, Any]:
    """Authenticate the implementation freeze an ARM names."""

    head, tree = gitauth.require_commit_tree(
        freeze_head, freeze_tree, label="implementation_freeze"
    )
    freeze = _load_tracked_json(head, freeze_relpath, label="IMPLEMENTATION_FREEZE")

    if freeze.get("research_id") != RESEARCH_ID:
        raise Market06LifecycleError("MARKET_06_FREEZE_RESEARCH_ID")

    prereg = freeze.get("prereg_authority") or {}
    if prereg.get("prereg_freeze_head") != PREREG_FREEZE_HEAD:
        raise Market06LifecycleError("MARKET_06_FREEZE_PREREG_HEAD")
    if prereg.get("prereg_freeze_tree") != PREREG_FREEZE_TREE:
        raise Market06LifecycleError("MARKET_06_FREEZE_PREREG_TREE")
    if prereg.get("prereg_content_head") != PREREG_CONTENT_HEAD:
        raise Market06LifecycleError("MARKET_06_FREEZE_PREREG_CONTENT_HEAD")

    data = freeze.get("data_authority") or {}
    if data.get("dataset_id") != DATASET_ID:
        raise Market06LifecycleError("MARKET_06_FREEZE_DATASET_ID")
    if data.get("snapshot_id") != SNAPSHOT_ID:
        raise Market06LifecycleError("MARKET_06_FREEZE_SNAPSHOT_ID")
    if data.get("durable_evidence_root_sha256") != DURABLE_EVIDENCE_ROOT_SHA256:
        raise Market06LifecycleError("MARKET_06_FREEZE_DURABLE_ROOT")

    impl_head = freeze.get("implementation_head")
    impl_tree = freeze.get("implementation_tree")
    if not isinstance(impl_head, str) or not isinstance(impl_tree, str):
        raise Market06LifecycleError("MARKET_06_FREEZE_NO_IMPLEMENTATION_BINDING")
    gitauth.require_commit_tree(impl_head, impl_tree, label="implementation")

    inventory = freeze.get("module_sha256")
    if not isinstance(inventory, dict) or not inventory:
        raise Market06LifecycleError("MARKET_06_FREEZE_NO_MODULE_INVENTORY")
    missing = set(SCIENTIFIC_MODULE_RELPATHS) - set(inventory)
    if missing:
        raise Market06LifecycleError(
            f"MARKET_06_FREEZE_INVENTORY_INCOMPLETE:{sorted(missing)[0]}"
        )

    # The bytes bound by the freeze must be the bytes recorded in the
    # implementation commit it names.
    for rel in SCIENTIFIC_MODULE_RELPATHS:
        committed = _sha256(gitauth.cat_blob(impl_head, rel))
        if committed != inventory[rel]:
            raise Market06LifecycleError(f"MARKET_06_FREEZE_INVENTORY_MISMATCH:{rel}")

    return {
        "implementation_freeze_head": head,
        "implementation_freeze_tree": tree,
        "implementation_head": impl_head,
        "implementation_tree": impl_tree,
        "module_sha256": dict(inventory),
    }


def _require_no_scientific_drift(impl_freeze_head: str, arm_commit: str) -> None:
    """No scientific module may change between freeze and ARM authority."""

    for rel in SCIENTIFIC_MODULE_RELPATHS:
        at_freeze = _sha256(gitauth.cat_blob(impl_freeze_head, rel))
        at_arm = _sha256(gitauth.cat_blob(arm_commit, rel))
        if at_freeze != at_arm:
            raise Market06ExecutionNotAuthorized(
                f"MARKET_06_SCIENTIFIC_MODULE_DRIFT:{rel}"
            )


def verify_execution_arm(
    *args: Any,
    arm_commit: str | None = None,
    **kwargs: Any,
) -> ExecutionPermit:
    """Authenticate a tracked ARM and mint an execution permit.

    ``arm_commit`` selects which immutable commit to read the ARM from
    (default: current ``HEAD`` commit object). It cannot supply ARM content,
    relax any check, or substitute identity.
    """

    reject_caller_authority_override(args, kwargs)
    if env_bypass_attempted():
        raise Market06ExecutionNotAuthorized(
            "environment variables cannot authorize MARKET-06 execution"
        )

    if arm_commit is None:
        proc = gitauth.git("rev-parse", "--verify", "--quiet", "HEAD^{commit}")
        if proc.returncode != 0:
            raise Market06ExecutionNotAuthorized("MARKET_06_NO_HEAD_COMMIT")
        arm_commit = proc.stdout.decode("ascii").strip()
    resolved_arm_commit = gitauth.require_commit(arm_commit, label="arm_commit")

    if not gitauth.blob_exists(resolved_arm_commit, ARM_JSON_REL):
        raise Market06ExecutionNotAuthorized("MARKET_06_NO_TRACKED_ARM")

    arm = _load_tracked_json(resolved_arm_commit, ARM_JSON_REL, label="ARM")

    for field in ARM_REQUIRED_FIELDS:
        if field not in arm:
            raise Market06LifecycleError(f"MARKET_06_ARM_FIELD_MISSING:{field}")

    if arm["research_id"] != RESEARCH_ID:
        raise Market06LifecycleError("MARKET_06_ARM_RESEARCH_ID")
    if arm["authorization_kind"] != AUTHORIZATION_KIND:
        raise Market06LifecycleError("MARKET_06_ARM_AUTHORIZATION_KIND")
    if arm["prereg_freeze_head"] != PREREG_FREEZE_HEAD:
        raise Market06LifecycleError("MARKET_06_ARM_PREREG_FREEZE_HEAD")
    if arm["prereg_freeze_tree"] != PREREG_FREEZE_TREE:
        raise Market06LifecycleError("MARKET_06_ARM_PREREG_FREEZE_TREE")
    if arm["dataset_id"] != DATASET_ID:
        raise Market06LifecycleError("MARKET_06_ARM_DATASET_ID")
    if arm["snapshot_id"] != SNAPSHOT_ID:
        raise Market06LifecycleError("MARKET_06_ARM_SNAPSHOT_ID")
    if arm["durable_evidence_root_sha256"] != DURABLE_EVIDENCE_ROOT_SHA256:
        raise Market06LifecycleError("MARKET_06_ARM_DURABLE_ROOT")
    if arm["scientific_outcomes_inspected_before_arm"] is not False:
        raise Market06LifecycleError("MARKET_06_ARM_OUTCOMES_INSPECTED")
    if arm["protected_2025_opened"] is not False:
        raise Market06LifecycleError("MARKET_06_ARM_2025_OPENED")
    if arm["protected_2026_opened"] is not False:
        raise Market06LifecycleError("MARKET_06_ARM_2026_OPENED")

    freeze_relpath = arm.get("implementation_freeze_relpath")
    if not isinstance(freeze_relpath, str) or not freeze_relpath:
        raise Market06LifecycleError("MARKET_06_ARM_NO_FREEZE_RELPATH")

    freeze = verify_implementation_freeze(
        arm["implementation_freeze_head"],
        arm["implementation_freeze_tree"],
        freeze_relpath,
    )

    module_root = arm.get("implementation_module_root")
    if not isinstance(module_root, str) or not module_root:
        raise Market06LifecycleError("MARKET_06_ARM_NO_MODULE_ROOT")
    for rel in SCIENTIFIC_MODULE_RELPATHS:
        if not rel.startswith(module_root):
            raise Market06LifecycleError(f"MARKET_06_ARM_MODULE_ROOT_MISMATCH:{rel}")

    # The bytes executing right now must be exactly the frozen bytes.
    live = live_module_sha256()
    for rel in SCIENTIFIC_MODULE_RELPATHS:
        if live[rel] != freeze["module_sha256"][rel]:
            raise Market06ExecutionNotAuthorized(
                f"MARKET_06_LIVE_MODULE_BYTES_DIFFER_FROM_FREEZE:{rel}"
            )

    gitauth.require_ancestor(
        freeze["implementation_freeze_head"],
        resolved_arm_commit,
        label="arm_must_descend_from_implementation_freeze",
    )
    _require_no_scientific_drift(freeze["implementation_freeze_head"], resolved_arm_commit)

    derived = derive_run_identity(live)
    if arm["run_identity"] != derived:
        raise Market06ExecutionNotAuthorized("MARKET_06_ARM_RUN_IDENTITY_MISMATCH")

    if arm.get("one_shot") is not True:
        raise Market06LifecycleError("MARKET_06_ARM_NOT_ONE_SHOT")

    require_no_existing_result(derived, commit=resolved_arm_commit)

    return ExecutionPermit(
        run_identity=derived,
        arm_commit=resolved_arm_commit,
        implementation_freeze_head=freeze["implementation_freeze_head"],
        implementation_freeze_tree=freeze["implementation_freeze_tree"],
        dataset_id=DATASET_ID,
        snapshot_id=SNAPSHOT_ID,
        durable_evidence_root_sha256=DURABLE_EVIDENCE_ROOT_SHA256,
        authorization_kind=AUTHORIZATION_KIND,
        _token=_PERMIT_TOKEN,
    )


def require_no_existing_result(run_identity: str, *, commit: str) -> None:
    """A canonical RESULT for this run identity makes a second run illegal."""

    if not gitauth.blob_exists(commit, RESULT_JSON_REL):
        return
    result = _load_tracked_json(commit, RESULT_JSON_REL, label="RESULT")
    if result.get("run_identity") == run_identity:
        raise Market06ExecutionNotAuthorized(
            "MARKET_06_CANONICAL_RUN_ALREADY_CONSUMED"
        )


def verify_execution_reservation(permit: Any, *, commit: str | None = None) -> dict[str, Any]:
    """A tracked, unconsumed reservation is required before any science."""

    authenticated = require_permit(permit)
    target_commit = commit or authenticated.arm_commit
    if not gitauth.blob_exists(target_commit, RESERVATION_JSON_REL):
        raise Market06ExecutionNotAuthorized("MARKET_06_NO_TRACKED_RESERVATION")
    reservation = _load_tracked_json(
        target_commit, RESERVATION_JSON_REL, label="RESERVATION"
    )
    if reservation.get("research_id") != RESEARCH_ID:
        raise Market06LifecycleError("MARKET_06_RESERVATION_RESEARCH_ID")
    if reservation.get("run_identity") != authenticated.run_identity:
        raise Market06LifecycleError("MARKET_06_RESERVATION_RUN_IDENTITY")
    if reservation.get("arm_commit") != authenticated.arm_commit:
        raise Market06LifecycleError("MARKET_06_RESERVATION_ARM_COMMIT")
    if reservation.get("implementation_freeze_head") != authenticated.implementation_freeze_head:
        raise Market06LifecycleError("MARKET_06_RESERVATION_FREEZE_HEAD")
    if reservation.get("dataset_id") != DATASET_ID:
        raise Market06LifecycleError("MARKET_06_RESERVATION_DATASET_ID")
    if reservation.get("snapshot_id") != SNAPSHOT_ID:
        raise Market06LifecycleError("MARKET_06_RESERVATION_SNAPSHOT_ID")
    if reservation.get("consumed") is not False:
        raise Market06ExecutionNotAuthorized("MARKET_06_RESERVATION_ALREADY_CONSUMED")
    targets = reservation.get("result_target_paths")
    if not isinstance(targets, list) or RESULT_JSON_REL not in targets:
        raise Market06LifecycleError("MARKET_06_RESERVATION_RESULT_TARGETS")
    require_no_existing_result(authenticated.run_identity, commit=target_commit)
    return reservation


class Market06ExecutionLock:
    """Atomic local lock guarding accidental double invocation.

    Scope note: this is a single-checkout, single-filesystem advisory lock
    created with ``O_CREAT | O_EXCL``. It is NOT a distributed mutex and
    provides no protection across machines, containers, or clones. The
    authoritative one-shot guarantees are the tracked reservation and the
    tracked RESULT, not this lock.
    """

    def __init__(self, run_identity: str) -> None:
        self.run_identity = run_identity
        self.path: Path = gitauth.repo_root() / EXECUTION_LOCK_REL
        self._fd: int | None = None

    def __enter__(self) -> "Market06ExecutionLock":
        try:
            self._fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError as exc:
            raise Market06ExecutionNotAuthorized(
                "MARKET_06_EXECUTION_LOCK_HELD"
            ) from exc
        os.write(self._fd, (self.run_identity + "\n").encode("utf-8"))
        os.fsync(self._fd)
        return self

    def __exit__(self, *exc_info: Any) -> None:
        if self._fd is not None:
            os.close(self._fd)
            self._fd = None
        try:
            self.path.unlink()
        except FileNotFoundError:  # pragma: no cover - already removed
            pass


def canonical_execution_permit_or_refuse(*args: Any, **kwargs: Any) -> ExecutionPermit:
    """Single entry point for canonical execution authorization.

    Refuses today (no tracked ARM exists). Succeeds unchanged once a valid
    tracked ARM exists, without editing any scientific module.
    """

    return verify_execution_arm(*args, **kwargs)


def inspect_lifecycle_state(*, commit: str | None = None) -> dict[str, Any]:
    """Non-raising, outcome-blind lifecycle status. No science."""

    state: dict[str, Any] = {
        "research_id": RESEARCH_ID,
        "arm_exists": False,
        "reservation_exists": False,
        "result_exists": False,
        "execution_authorized": False,
        "scientific_outcomes_inspected": False,
    }
    try:
        if commit is None:
            proc = gitauth.git("rev-parse", "--verify", "--quiet", "HEAD^{commit}")
            if proc.returncode != 0:
                return state
            commit = proc.stdout.decode("ascii").strip()
        state["arm_exists"] = gitauth.blob_exists(commit, ARM_JSON_REL)
        state["reservation_exists"] = gitauth.blob_exists(commit, RESERVATION_JSON_REL)
        state["result_exists"] = gitauth.blob_exists(commit, RESULT_JSON_REL)
        try:
            verify_execution_arm(arm_commit=commit)
            state["execution_authorized"] = True
        except (Market06ExecutionNotAuthorized, Market06LifecycleError,
                Market06GitAuthorityError):
            state["execution_authorized"] = False
    except Market06GitAuthorityError:
        return state
    return state
