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
CLAIM_JSON_REL = "docs/research/MARKET_06_EXECUTION_CLAIM.json"
RESULT_JSON_REL = "docs/research/MARKET_06_CROSS_VENUE_DISLOCATION_RESULT.json"
RESULT_MD_REL = "docs/research/MARKET_06_CROSS_VENUE_DISLOCATION_RESULT.md"

EXECUTION_LOCK_REL = ".market_06_canonical_execution.lock"
# Durable local record that the one shot was actually taken. Unlike the
# lock it is NEVER removed on failure (red-team L11): a crash after the
# claim must not silently return the shot.
EXECUTION_ATTEMPT_LEDGER_REL = ".market_06_canonical_execution_attempts.json"

CLAIM_STATE_CLAIMED = "CANONICAL_EXECUTION_CLAIMED"

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
    "scripts/research/market_06_result_persistence.py",
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
        "source_commit",
        "source_ref",
        "data_commit",
        "dataset_commit",
        "reservation",
        "claim",
    }
)

RESERVATION_REQUIRED_FIELDS: tuple[str, ...] = (
    "research_id",
    "run_identity",
    "arm_commit",
    "implementation_freeze_head",
    "implementation_freeze_tree",
    "dataset_id",
    "snapshot_id",
    "durable_evidence_root_sha256",
    "authorization_kind",
    "result_target_paths",
    "claim_target_path",
    "consumed",
    "scientific_outcomes_inspected_before_reservation",
    "protected_2025_opened",
    "protected_2026_opened",
)

CLAIM_REQUIRED_FIELDS: tuple[str, ...] = (
    "research_id",
    "run_identity",
    "arm_commit",
    "reservation_commit",
    "implementation_freeze_head",
    "implementation_freeze_tree",
    "dataset_id",
    "snapshot_id",
    "durable_evidence_root_sha256",
    "claim_state",
    "result_target_paths",
    "protected_2025_opened",
    "protected_2026_opened",
)

# An artifact must never carry its own commit SHA: its authority is the
# commit it is read FROM (red-team L10).
SELF_REFERENTIAL_FIELDS = (
    "reservation_commit_sha",
    "claim_commit_sha",
    "self_commit",
    "own_commit",
    "this_commit",
)

BYPASS_ENV_KEYS = (
    "MARKET_06_EXECUTE",
    "MARKET_06_AUTHORIZATION",
    "MARKET_06_FORCE",
    "MARKET_06_ARM",
    "MARKET_06_PERMIT",
    "MARKET_06_CLAIM",
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
        # The ARM is identified by the reservation, never by searching HEAD
        # (red-team L10). Refuse rather than guess.
        raise Market06ExecutionNotAuthorized("MARKET_06_ARM_COMMIT_REQUIRED")
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


def _reject_self_referential(payload: Mapping[str, Any], *, label: str) -> None:
    """An artifact may not carry its own commit SHA (red-team L10)."""

    for field in SELF_REFERENTIAL_FIELDS:
        if field in payload:
            raise Market06LifecycleError(
                f"MARKET_06_{label}_SELF_REFERENTIAL_FIELD:{field}"
            )


def verify_execution_reservation_from_commit(
    reservation_commit: str,
) -> tuple[ExecutionPermit, dict[str, Any], str]:
    """Authority chain RESERVATION -> ARM -> IMPLEMENTATION FREEZE.

    The reservation is authoritative because of the commit it is READ FROM,
    so it never contains its own commit SHA. It names its ARM commit; the
    ARM is authenticated at exactly that commit (red-team L10).
    """

    resolved = gitauth.require_commit(reservation_commit, label="reservation_commit")
    if not gitauth.blob_exists(resolved, RESERVATION_JSON_REL):
        raise Market06ExecutionNotAuthorized("MARKET_06_NO_TRACKED_RESERVATION")
    reservation = _load_tracked_json(resolved, RESERVATION_JSON_REL, label="RESERVATION")

    for field in RESERVATION_REQUIRED_FIELDS:
        if field not in reservation:
            raise Market06LifecycleError(f"MARKET_06_RESERVATION_FIELD_MISSING:{field}")
    _reject_self_referential(reservation, label="RESERVATION")

    arm_commit = reservation["arm_commit"]
    if not isinstance(arm_commit, str):
        raise Market06LifecycleError("MARKET_06_RESERVATION_ARM_COMMIT_TYPE")

    permit = verify_execution_arm(arm_commit=arm_commit)

    gitauth.require_ancestor(
        permit.arm_commit, resolved, label="arm_must_precede_reservation"
    )

    if reservation["research_id"] != RESEARCH_ID:
        raise Market06LifecycleError("MARKET_06_RESERVATION_RESEARCH_ID")
    if reservation["run_identity"] != permit.run_identity:
        raise Market06LifecycleError("MARKET_06_RESERVATION_RUN_IDENTITY")
    if reservation["implementation_freeze_head"] != permit.implementation_freeze_head:
        raise Market06LifecycleError("MARKET_06_RESERVATION_FREEZE_HEAD")
    if reservation["implementation_freeze_tree"] != permit.implementation_freeze_tree:
        raise Market06LifecycleError("MARKET_06_RESERVATION_FREEZE_TREE")
    if reservation["dataset_id"] != DATASET_ID:
        raise Market06LifecycleError("MARKET_06_RESERVATION_DATASET_ID")
    if reservation["snapshot_id"] != SNAPSHOT_ID:
        raise Market06LifecycleError("MARKET_06_RESERVATION_SNAPSHOT_ID")
    if reservation["durable_evidence_root_sha256"] != DURABLE_EVIDENCE_ROOT_SHA256:
        raise Market06LifecycleError("MARKET_06_RESERVATION_DURABLE_ROOT")
    if reservation["authorization_kind"] != AUTHORIZATION_KIND:
        raise Market06LifecycleError("MARKET_06_RESERVATION_AUTHORIZATION_KIND")
    if reservation["scientific_outcomes_inspected_before_reservation"] is not False:
        raise Market06LifecycleError("MARKET_06_RESERVATION_OUTCOMES_INSPECTED")
    if reservation["protected_2025_opened"] is not False:
        raise Market06LifecycleError("MARKET_06_RESERVATION_2025_OPENED")
    if reservation["protected_2026_opened"] is not False:
        raise Market06LifecycleError("MARKET_06_RESERVATION_2026_OPENED")
    if reservation["consumed"] is not False:
        raise Market06ExecutionNotAuthorized("MARKET_06_RESERVATION_ALREADY_CONSUMED")
    targets = reservation["result_target_paths"]
    if not isinstance(targets, list) or RESULT_JSON_REL not in targets:
        raise Market06LifecycleError("MARKET_06_RESERVATION_RESULT_TARGETS")
    if reservation["claim_target_path"] != CLAIM_JSON_REL:
        raise Market06LifecycleError("MARKET_06_RESERVATION_CLAIM_TARGET")

    require_no_existing_result(permit.run_identity, commit=resolved)
    return permit, reservation, resolved


@dataclass(frozen=True)
class ClaimAuthority:
    """Fully resolved CLAIM -> RESERVATION -> ARM -> FREEZE authority."""

    permit: ExecutionPermit
    reservation: dict[str, Any]
    claim: dict[str, Any]
    arm_commit: str
    reservation_commit: str
    claim_commit: str

    @property
    def run_identity(self) -> str:
        return self.permit.run_identity


def verify_claim_from_commit(claim_commit: str) -> ClaimAuthority:
    """Authenticate the durable pre-science CLAIM and the whole chain.

    The claim is the DURABLE consumption point (red-team L11): it must
    exist before any market data is parsed, so a crash between outcome
    computation and RESULT persistence cannot silently return the one shot.
    """

    resolved = gitauth.require_commit(claim_commit, label="claim_commit")
    if not gitauth.blob_exists(resolved, CLAIM_JSON_REL):
        raise Market06ExecutionNotAuthorized("MARKET_06_NO_TRACKED_CLAIM")
    claim = _load_tracked_json(resolved, CLAIM_JSON_REL, label="CLAIM")

    for field in CLAIM_REQUIRED_FIELDS:
        if field not in claim:
            raise Market06LifecycleError(f"MARKET_06_CLAIM_FIELD_MISSING:{field}")
    _reject_self_referential(claim, label="CLAIM")

    reservation_commit = claim["reservation_commit"]
    if not isinstance(reservation_commit, str):
        raise Market06LifecycleError("MARKET_06_CLAIM_RESERVATION_COMMIT_TYPE")

    permit, reservation, resolved_reservation = verify_execution_reservation_from_commit(
        reservation_commit
    )

    gitauth.require_ancestor(
        resolved_reservation, resolved, label="reservation_must_precede_claim"
    )

    if claim["research_id"] != RESEARCH_ID:
        raise Market06LifecycleError("MARKET_06_CLAIM_RESEARCH_ID")
    if claim["run_identity"] != permit.run_identity:
        raise Market06LifecycleError("MARKET_06_CLAIM_RUN_IDENTITY")
    if claim["arm_commit"] != permit.arm_commit:
        raise Market06LifecycleError("MARKET_06_CLAIM_ARM_COMMIT")
    if claim["implementation_freeze_head"] != permit.implementation_freeze_head:
        raise Market06LifecycleError("MARKET_06_CLAIM_FREEZE_HEAD")
    if claim["implementation_freeze_tree"] != permit.implementation_freeze_tree:
        raise Market06LifecycleError("MARKET_06_CLAIM_FREEZE_TREE")
    if claim["dataset_id"] != DATASET_ID:
        raise Market06LifecycleError("MARKET_06_CLAIM_DATASET_ID")
    if claim["snapshot_id"] != SNAPSHOT_ID:
        raise Market06LifecycleError("MARKET_06_CLAIM_SNAPSHOT_ID")
    if claim["durable_evidence_root_sha256"] != DURABLE_EVIDENCE_ROOT_SHA256:
        raise Market06LifecycleError("MARKET_06_CLAIM_DURABLE_ROOT")
    if claim["claim_state"] != CLAIM_STATE_CLAIMED:
        raise Market06LifecycleError("MARKET_06_CLAIM_STATE")
    if claim["protected_2025_opened"] is not False:
        raise Market06LifecycleError("MARKET_06_CLAIM_2025_OPENED")
    if claim["protected_2026_opened"] is not False:
        raise Market06LifecycleError("MARKET_06_CLAIM_2026_OPENED")
    targets = claim["result_target_paths"]
    if not isinstance(targets, list) or RESULT_JSON_REL not in targets:
        raise Market06LifecycleError("MARKET_06_CLAIM_RESULT_TARGETS")
    for forbidden in ("classification", "gates", "outcome", "result"):
        if forbidden in claim:
            raise Market06LifecycleError(f"MARKET_06_CLAIM_CARRIES_OUTCOME:{forbidden}")

    require_no_existing_result(permit.run_identity, commit=resolved)

    return ClaimAuthority(
        permit=permit,
        reservation=reservation,
        claim=claim,
        arm_commit=permit.arm_commit,
        reservation_commit=resolved_reservation,
        claim_commit=resolved,
    )


def assert_claim_creatable(run_identity: str, *, commit: str) -> None:
    """A second claim for the same run identity is refused (one shot)."""

    if not gitauth.blob_exists(commit, CLAIM_JSON_REL):
        return
    claim = _load_tracked_json(commit, CLAIM_JSON_REL, label="CLAIM")
    if claim.get("run_identity") == run_identity:
        raise Market06ExecutionNotAuthorized(
            "MARKET_06_CANONICAL_RUN_ALREADY_CLAIMED"
        )


# ---------------------------------------------------------------------------
# Durable local attempt ledger.
#
# The tracked CLAIM records that the shot was authorized; this ledger records
# that a process actually began consuming it. It is fsynced before any market
# data is parsed and is NEVER removed on failure, so a crash after the claim
# cannot silently return the shot (red-team L11). Scope: this checkout only.
# ---------------------------------------------------------------------------


def _attempt_ledger_path() -> Path:
    return gitauth.repo_root() / EXECUTION_ATTEMPT_LEDGER_REL


def read_attempt_ledger() -> dict[str, Any]:
    path = _attempt_ledger_path()
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise Market06LifecycleError("MARKET_06_ATTEMPT_LEDGER_MALFORMED") from exc
    return payload if isinstance(payload, dict) else {}


def assert_shot_not_already_consumed(run_identity: str) -> None:
    ledger = read_attempt_ledger()
    if run_identity in ledger:
        raise Market06ExecutionNotAuthorized(
            "MARKET_06_CANONICAL_RUN_ALREADY_CLAIMED"
        )


def record_execution_attempt(authority: "ClaimAuthority") -> None:
    """Durably consume the shot BEFORE any science. Never rolled back."""

    ledger = read_attempt_ledger()
    if authority.run_identity in ledger:
        raise Market06ExecutionNotAuthorized(
            "MARKET_06_CANONICAL_RUN_ALREADY_CLAIMED"
        )
    ledger[authority.run_identity] = {
        "claim_commit": authority.claim_commit,
        "reservation_commit": authority.reservation_commit,
        "arm_commit": authority.arm_commit,
        "claim_state": CLAIM_STATE_CLAIMED,
        "scientific_outcomes_inspected": False,
    }
    path = _attempt_ledger_path()
    tmp = path.with_suffix(path.suffix + ".tmp")
    data = canonical_json_bytes(ledger)
    with open(tmp, "wb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, path)
    directory = os.open(str(path.parent), os.O_DIRECTORY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


def resolve_canonical_authority(*, head: str | None = None) -> ClaimAuthority:
    """Top-level: HEAD -> CLAIM -> RESERVATION -> ARM -> FREEZE."""

    if head is None:
        proc = gitauth.git("rev-parse", "--verify", "--quiet", "HEAD^{commit}")
        if proc.returncode != 0:
            raise Market06ExecutionNotAuthorized("MARKET_06_NO_HEAD_COMMIT")
        head = proc.stdout.decode("ascii").strip()
    return verify_claim_from_commit(head)


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


def canonical_execution_permit_or_refuse(*args: Any, **kwargs: Any) -> ClaimAuthority:
    """Single entry point for canonical execution authorization.

    Canonical science now requires a durable tracked CLAIM, not merely an
    ARM (red-team L11). Refuses today because no claim exists. Succeeds
    unchanged once CLAIM -> RESERVATION -> ARM -> FREEZE is tracked, with
    no edit to any scientific module.
    """

    reject_caller_authority_override(args, kwargs)
    if env_bypass_attempted():
        raise Market06ExecutionNotAuthorized(
            "environment variables cannot authorize MARKET-06 execution"
        )
    return resolve_canonical_authority(**kwargs)


def inspect_lifecycle_state(*, commit: str | None = None) -> dict[str, Any]:
    """Non-raising, outcome-blind lifecycle status. No science."""

    state: dict[str, Any] = {
        "research_id": RESEARCH_ID,
        "arm_exists": False,
        "reservation_exists": False,
        "claim_exists": False,
        "result_exists": False,
        "execution_authorized": False,
        "authority_chain": "CLAIM -> RESERVATION -> ARM -> IMPLEMENTATION_FREEZE",
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
        state["claim_exists"] = gitauth.blob_exists(commit, CLAIM_JSON_REL)
        state["result_exists"] = gitauth.blob_exists(commit, RESULT_JSON_REL)
        try:
            verify_claim_from_commit(commit)
            state["execution_authorized"] = True
        except (Market06ExecutionNotAuthorized, Market06LifecycleError,
                Market06GitAuthorityError):
            state["execution_authorized"] = False
    except Market06GitAuthorityError:
        return state
    return state
