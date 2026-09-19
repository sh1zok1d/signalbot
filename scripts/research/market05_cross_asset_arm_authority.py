"""MARKET-05 ARM-lifecycle authority.

Repairs the pre-ARM lifecycle gate: the SAME frozen scientific
implementation that is reviewed while UNARMED becomes authorized once an
authenticated ARM + RESERVATION pair exists, with no source modification.

This module does not evaluate MARKET-05 outcomes and does not read CORE
BTC/ETH scientific rows. It only decides authorization.

Design rules (adapted from the established MARKET-03 ARM authority):

* RUN_IDENTITY is RECOMPUTED here from frozen constants. An ARM that
  merely *contains* a run_identity proves nothing; it must equal the
  independently derived value.
* No pre-pinned ARM hash. MARKET-05 is pre-ARM, so the ARM is
  authenticated by bound CONTENT, not by a hash that cannot yet exist.
* The ARM cannot redefine scientific parameters: every scientific
  constant it carries must equal the frozen value, and any outcome-shaped
  field is rejected outright.
* Caller arguments can never substitute authority.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any, Mapping


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


RESEARCH_ID = "MARKET-05_CROSS_ASSET_CONFIRMATION_ADVERSE_PATH_RISK"
UNIT_ID = "MARKET_05_CROSS_ASSET_ARM"

PREREG_MD_REL = "docs/research/MARKET_05_CROSS_ASSET_PREREG.md"
PREREG_JSON_REL = "docs/research/MARKET_05_CROSS_ASSET_PREREG.json"
REFREEZE_MD_REL = "docs/research/MARKET_05_IMPLEMENTATION_REFREEZE.md"
REFREEZE_JSON_REL = "docs/research/MARKET_05_IMPLEMENTATION_REFREEZE.json"
ARM_CONTRACT_MD_REL = "docs/research/MARKET_05_ARM_CONTRACT.md"
ARM_CONTRACT_JSON_REL = "docs/research/MARKET_05_ARM_CONTRACT.json"
ARM_JSON_REL = "docs/research/MARKET_05_ARM.json"
ARM_MD_REL = "docs/research/MARKET_05_ARM.md"
RESERVATION_JSON_REL = "docs/research/MARKET_05_RESERVATION.json"
RESULT_JSON_REL = "docs/research/MARKET_05_RESULT.json"
RESULT_MD_REL = "docs/research/MARKET_05_RESULT.md"

LIB_REL = "scripts/research/market05_cross_asset_lib.py"
AUTHORITY_REL = "scripts/research/market05_cross_asset_authority.py"
ARM_AUTHORITY_REL = "scripts/research/market05_cross_asset_arm_authority.py"
CLI_REL = "scripts/research/market05_cross_asset.py"
DATA_REL = "scripts/research/market05_cross_asset_data.py"
EXECUTION_REL = "scripts/research/market05_cross_asset_canonical_execution.py"
AUTHORITY_ROOT_REL = "scripts/research/market05_cross_asset_authority_root.py"
ETH_ACCEPTOR_LIB_REL = "scripts/research/core_eth_binance_v0_acceptor_lib.py"

BTC_SNAPSHOT_DOC_REL = "docs/research_data/CORE_BTC_BINANCE_V0/SNAPSHOT_717d37a4.json"
ETH_SNAPSHOT_DOC_REL = "docs/research_data/CORE_ETH_BINANCE_V0/SNAPSHOT_4b9c113f.json"

FROZEN_PREREG_MD_SHA256 = (
    "31349f8863be3a79604d0c8dc93ca7037451ab16edb83a432d31af81f8a0193e"
)
FROZEN_PREREG_JSON_SHA256 = (
    "f2b2f6b98a3674412b584e6bd2686efa8fb9ce08b5d936e503e5d570a2428b25"
)
FROZEN_PREREG_HEAD = "5b2a582cd3c42af7114ded7fe61ac7c9f39c9dd5"
PREVIOUS_IMPLEMENTATION_HEAD = "0016e4fc616af9222f9c9fd581a4a4199b1bdccf"
PREVIOUS_IMPLEMENTATION_TREE = "9c8575f6380977de2b2ad0d4d4c935ad819da6ef"

BTC_DATASET_ID = "CORE_BTC_BINANCE_V0"
BTC_SNAPSHOT_ID = "717d37a404f81eefd58c9a796cc11868c48226baf1de8ffecad5e5607f8dd415"
ETH_DATASET_ID = "CORE_ETH_BINANCE_V0"
ETH_SNAPSHOT_ID = "4b9c113f659e1c1ca71498096dfdc2628a1016346aed40e19020efb64c85ad15"

DEVELOPMENT_START_INCLUSIVE = "2020-01-03T00:00:00Z"
DEVELOPMENT_END_EXCLUSIVE = "2025-01-01T00:00:00Z"
PROTECTED_OOS_START = "2025-01-01T00:00:00Z"
PROTECTED_OOS_AUTHORIZED = False

NUMPY_PINNED_VERSION = "2.1.3"

# Frozen scientific constants. The ARM must reproduce these EXACTLY; it has
# no authority to redefine any of them.
SCIENTIFIC_CONSTANTS: dict[str, Any] = {
    "decision_time": "00:00:00 UTC",
    "decision_frequency": "DAILY",
    "feature_lookback_hours": 24,
    "outcome_horizon_hours": 24,
    "eth_confirmation": "BTC_SIDE * Z_ETH",
    "primary_outcome": "BTC_DIRECTION_ALIGNED_MAE_24H",
    "baseline_model": "Y ~ BTC_SIDE + ABS_Z_BTC + RV_BTC_24H",
    "candidate_model": "Y ~ BTC_SIDE + ABS_Z_BTC + RV_BTC_24H + ETH_CONFIRMATION",
    "model": "OLS",
    "materiality": 0.02,
    "bootstrap_kind": "CIRCULAR_MOVING_BLOCK",
    "block_length": 14,
    "bootstrap_replicates": 5000,
    "random_seed": 2026091905,
    "predictive_bootstrap_refit": False,
    "coefficient_bootstrap_refit": True,
    "ci": "2.5th / 97.5th percentiles",
    "rng": "SplitMix64",
    "std_ddof": 0,
}

# Every file able to materially change a MARKET-05 scientific result.
# Filled by the re-freeze; authenticated byte-for-byte before authorization.
# This module cannot pin its own hash (self-reference); the ARM CONTRACT and
# the re-freeze artifact bind ARM_AUTHORITY_REL instead.
SCIENTIFIC_IMPLEMENTATION_HASHES: dict[str, str] = {
    LIB_REL: "b0e3f441d23f372efc18c94adaab033e9eb9a219654954e1312b42489cf61274",
    AUTHORITY_REL: "441f48f438ca6a240911bd3de8a8a96f1a9e93c1b182a4ebb0d2b09da26bb9fc",
    CLI_REL: "1a587d58c970e99c5db49478f89cfb5f040537658ff8034af403fa378f0a997c",
    DATA_REL: "f7a3b0ceed2e691716346a89e4800def29f2e7526559dda0407bb1d33d6c8357",
    EXECUTION_REL: "df9bf457d379a3810ce98b06545b138fc813aa9b8fa49a48f11ca124f0f2c67d",
    ETH_ACCEPTOR_LIB_REL: (
        "6f86ae1ed08fe7595a0de3eb4e0c273aa2850a8238675d72696bbd088c118764"
    ),
}

# 1.1.0 separates commit provenance (implementation_head/implementation_tree,
# exact git SHAs) from per-file identity (scientific_implementation_hashes).
RESULT_SCHEMA_IDENTITY = "market_05_cross_asset_result/1.1.0"

CANONICAL_EXECUTIONS_AUTHORIZED_EXPECTED = 1

# Any of these appearing in an ARM means the ARM is carrying outcomes.
ARM_FORBIDDEN_OUTCOME_FIELDS = (
    "classification",
    "gates",
    "coefficients",
    "bootstrap",
    "bootstrap_cis",
    "maes",
    "mae_baseline",
    "mae_candidate",
    "relative_mae_improvement",
    "year_metrics",
    "row_counts",
    "fold_counts",
    "exclusion_counts",
    "RESULT",
    "result",
    "eth_confirmation_coefficient",
    "final_classification",
)


class Market05ArmAuthorityError(RuntimeError):
    """ARM-authority or identity failure."""


class Market05CanonicalExecutionNotAuthorized(RuntimeError):
    def __init__(self, message: str = "MARKET_05_EXECUTION_NOT_AUTHORIZED") -> None:
        super().__init__(message)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_json_bytes(payload: Mapping[str, Any]) -> bytes:
    """Deterministic canonical serialization.

    sort_keys removes filesystem/dict-order dependence; allow_nan=False
    forbids non-finite values; no timestamp and no uuid are ever included.
    """
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


def _reject_caller_kwargs(args: tuple[Any, ...], kwargs: Mapping[str, Any]) -> None:
    if args or kwargs:
        raise Market05CanonicalExecutionNotAuthorized(
            "caller arguments cannot redefine MARKET-05 ARM authority"
        )


def _path(rel: str) -> Path:
    return _repo_root() / rel


def _require_regular_file(rel: str) -> Path:
    """Reject symlinks and non-regular authority files."""
    path = _path(rel)
    if path.is_symlink():
        raise Market05ArmAuthorityError(f"MARKET_05_AUTHORITY_SYMLINK_REFUSED:{rel}")
    if not path.is_file():
        raise Market05CanonicalExecutionNotAuthorized(
            f"MARKET_05_AUTHORITY_FILE_MISSING:{rel}"
        )
    return path


def _load_json(rel: str) -> dict[str, Any]:
    path = _require_regular_file(rel)
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise Market05ArmAuthorityError(
            f"MARKET_05_AUTHORITY_MALFORMED_JSON:{rel}"
        ) from exc


def require_git_tracked_authority(rel: str) -> None:
    """Authority artifacts must be tracked, not dropped-in untracked files.

    Existence (and regular-file/symlink status) is checked first so a
    missing artifact reports MISSING rather than the less precise
    UNTRACKED.
    """
    _require_regular_file(rel)
    root = _repo_root()
    try:
        proc = subprocess.run(
            ["git", "ls-files", "--error-unmatch", "--", rel],
            cwd=str(root),
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as exc:
        raise Market05ArmAuthorityError("MARKET_05_GIT_UNAVAILABLE") from exc
    if proc.returncode != 0:
        raise Market05ArmAuthorityError(
            f"MARKET_05_AUTHORITY_FILE_UNTRACKED:{rel}"
        )


def scientific_run_identity_payload() -> dict[str, Any]:
    """Canonical RUN_IDENTITY preimage.

    Binds research identity, prereg identity, implementation identity,
    both dataset snapshots, the development window, every scientific and
    bootstrap constant, and the RESULT schema identity. Contains no clock
    reading, no uuid, and nothing derived from filesystem order.
    """
    return {
        "schema": "market_05_cross_asset_scientific_run_identity",
        "schema_version": "1.0.0",
        "research_id": RESEARCH_ID,
        "purpose": "CANONICAL_MARKET_05_EXECUTION",
        "prereg_head": FROZEN_PREREG_HEAD,
        "prereg_md_sha256": FROZEN_PREREG_MD_SHA256,
        "prereg_json_sha256": FROZEN_PREREG_JSON_SHA256,
        "scientific_implementation_hashes": dict(
            sorted(SCIENTIFIC_IMPLEMENTATION_HASHES.items())
        ),
        # The ARM authority itself is part of the bound identity. It cannot
        # pin its own hash here (self-reference), so RUN_IDENTITY binds the
        # authority-root module that carries its git blob id instead.
        "arm_authority_file": ARM_AUTHORITY_REL,
        "authority_root_file": AUTHORITY_ROOT_REL,
        "authority_root_blob_ids": _authority_root_blob_ids(),
        "btc_dataset_id": BTC_DATASET_ID,
        "btc_snapshot_id": BTC_SNAPSHOT_ID,
        "eth_dataset_id": ETH_DATASET_ID,
        "eth_snapshot_id": ETH_SNAPSHOT_ID,
        "development_window": {
            "start_inclusive": DEVELOPMENT_START_INCLUSIVE,
            "end_exclusive": DEVELOPMENT_END_EXCLUSIVE,
        },
        "protected_oos_start": PROTECTED_OOS_START,
        "protected_oos_authorized": False,
        "scientific_constants": dict(sorted(SCIENTIFIC_CONSTANTS.items())),
        "result_schema_identity": RESULT_SCHEMA_IDENTITY,
        "numpy_version": NUMPY_PINNED_VERSION,
        "canonical_executions_authorized": CANONICAL_EXECUTIONS_AUTHORIZED_EXPECTED,
    }


def derive_market_05_run_identity(*args: Any, **kwargs: Any) -> str:
    """Independently recompute RUN_IDENTITY. Never read from the ARM."""
    _reject_caller_kwargs(args, kwargs)
    return _sha256_bytes(canonical_json_bytes(scientific_run_identity_payload()))


def authenticate_frozen_prereg_bytes(*args: Any, **kwargs: Any) -> dict[str, str]:
    _reject_caller_kwargs(args, kwargs)
    md = sha256_file(_require_regular_file(PREREG_MD_REL))
    js = sha256_file(_require_regular_file(PREREG_JSON_REL))
    if md != FROZEN_PREREG_MD_SHA256 or js != FROZEN_PREREG_JSON_SHA256:
        raise Market05ArmAuthorityError("MARKET_05_PREREG_BYTE_IDENTITY_MISMATCH")
    return {"prereg_md_sha256": md, "prereg_json_sha256": js}


def _refusal_exceptions() -> tuple[type[BaseException], ...]:
    """Every exception class that means "not authorized", never a crash.

    Includes the authority-root failure, so a mutated authority module
    fails CLOSED (reported as unauthorized) instead of propagating.
    """
    from scripts.research.market05_cross_asset_authority_root import (
        Market05AuthorityRootError,
    )

    return (
        Market05ArmAuthorityError,
        Market05CanonicalExecutionNotAuthorized,
        Market05AuthorityRootError,
        OSError,
        json.JSONDecodeError,
    )


def _authority_root():
    """Lazily resolve the independent authority-root module."""
    from scripts.research import market05_cross_asset_authority_root as root

    return root


def _authority_root_blob_ids() -> dict[str, str]:
    """Git blob ids pinned by the authority root, including this module's.

    Bound into RUN_IDENTITY so the ARM authority's own bytes are part of
    the canonical identity without this module attesting to itself.
    """
    return dict(sorted(_authority_root().FROZEN_BLOB_IDS.items()))


def verify_authority_root(*args: Any, **kwargs: Any) -> dict[str, Any]:
    """Delegate to the independent root of trust."""
    _reject_caller_kwargs(args, kwargs)
    return _authority_root().verify_authority_root()


def authenticate_frozen_scientific_bytes(*args: Any, **kwargs: Any) -> dict[str, str]:
    """Every science-capable file must match the re-frozen bytes exactly.

    This is what makes post-ARM source mutation detectable.
    """
    _reject_caller_kwargs(args, kwargs)
    seen: dict[str, str] = {}
    for rel, expected in sorted(SCIENTIFIC_IMPLEMENTATION_HASHES.items()):
        digest = sha256_file(_require_regular_file(rel))
        if digest != expected:
            raise Market05ArmAuthorityError(
                f"MARKET_05_IMPLEMENTATION_BYTE_IDENTITY_MISMATCH:{rel}"
            )
        seen[rel] = digest
    return seen


def reject_protected_oos_authorization(payload: Mapping[str, Any]) -> None:
    """Even a valid development ARM may never open 2025-01-01T00:00:00Z onward."""
    if payload.get("protected_oos_authorized") not in (False, None):
        raise Market05ArmAuthorityError("MARKET_05_PROTECTED_OOS_AUTHORIZATION_REFUSED")
    if payload.get("PROTECTED_OOS_AUTHORIZED") not in (False, None):
        raise Market05ArmAuthorityError("MARKET_05_PROTECTED_OOS_AUTHORIZATION_REFUSED")
    end = payload.get("development_end_exclusive")
    if end is not None and end != DEVELOPMENT_END_EXCLUSIVE:
        raise Market05ArmAuthorityError("MARKET_05_PROTECTED_OOS_EXTENSION_REFUSED")
    if PROTECTED_OOS_AUTHORIZED is not False:
        raise Market05ArmAuthorityError("MARKET_05_PROTECTED_OOS_AUTHORIZED")


def _require_field(payload: Mapping[str, Any], key: str, expected: Any, code: str) -> None:
    if payload.get(key) != expected:
        raise Market05CanonicalExecutionNotAuthorized(f"{code}:{key}")


def authenticate_market_05_arm(*args: Any, **kwargs: Any) -> dict[str, Any]:
    """Authenticate the ARM artifact by bound content.

    Refuses: missing, malformed, untracked, symlinked, wrong research id,
    wrong prereg/implementation identity, wrong snapshots, wrong or absent
    run identity, redefined scientific constants, outcome-carrying fields,
    protected-OOS authorization, and already-consumed authorizations.
    """
    _reject_caller_kwargs(args, kwargs)
    # Independent root of trust FIRST: proves this module's own bytes are
    # the frozen ones before any of its decisions are relied upon.
    verify_authority_root()
    authenticate_frozen_prereg_bytes()
    authenticate_frozen_scientific_bytes()

    require_git_tracked_authority(ARM_JSON_REL)
    require_git_tracked_authority(ARM_MD_REL)
    payload = _load_json(ARM_JSON_REL)
    _require_regular_file(ARM_MD_REL)

    if payload.get("research_id") != RESEARCH_ID:
        raise Market05CanonicalExecutionNotAuthorized("MARKET_05_ARM_RESEARCH_ID_MISMATCH")

    for field in ARM_FORBIDDEN_OUTCOME_FIELDS:
        if field in payload:
            raise Market05ArmAuthorityError("MARKET_05_ARM_CONTAINS_OUTCOME_FIELD")

    _require_field(
        payload, "prereg_md_sha256", FROZEN_PREREG_MD_SHA256, "MARKET_05_ARM_PREREG_MISMATCH"
    )
    _require_field(
        payload,
        "prereg_json_sha256",
        FROZEN_PREREG_JSON_SHA256,
        "MARKET_05_ARM_PREREG_MISMATCH",
    )
    _require_field(
        payload, "btc_dataset_id", BTC_DATASET_ID, "MARKET_05_ARM_SNAPSHOT_MISMATCH"
    )
    _require_field(
        payload, "btc_snapshot_id", BTC_SNAPSHOT_ID, "MARKET_05_ARM_SNAPSHOT_MISMATCH"
    )
    _require_field(
        payload, "eth_dataset_id", ETH_DATASET_ID, "MARKET_05_ARM_SNAPSHOT_MISMATCH"
    )
    _require_field(
        payload, "eth_snapshot_id", ETH_SNAPSHOT_ID, "MARKET_05_ARM_SNAPSHOT_MISMATCH"
    )
    _require_field(
        payload,
        "result_schema_identity",
        RESULT_SCHEMA_IDENTITY,
        "MARKET_05_ARM_RESULT_SCHEMA_MISMATCH",
    )

    # The ARM may not redefine any scientific parameter.
    arm_constants = payload.get("scientific_constants")
    if arm_constants != SCIENTIFIC_CONSTANTS:
        raise Market05ArmAuthorityError("MARKET_05_ARM_SCIENTIFIC_CONSTANT_REDEFINED")

    arm_hashes = payload.get("scientific_implementation_hashes")
    if arm_hashes != SCIENTIFIC_IMPLEMENTATION_HASHES:
        raise Market05CanonicalExecutionNotAuthorized(
            "MARKET_05_ARM_IMPLEMENTATION_MISMATCH"
        )

    # Predeclared RESULT paths only.
    result_paths = payload.get("result_paths")
    if result_paths != {"json": RESULT_JSON_REL, "md": RESULT_MD_REL}:
        raise Market05CanonicalExecutionNotAuthorized("MARKET_05_ARM_RESULT_PATH_MISMATCH")

    reject_protected_oos_authorization(payload)

    # RUN_IDENTITY is recomputed, never trusted from the ARM.
    derived = derive_market_05_run_identity()
    if payload.get("run_identity") != derived:
        raise Market05CanonicalExecutionNotAuthorized("MARKET_05_ARM_RUN_IDENTITY_MISMATCH")

    if payload.get("MARKET_05_ARMED") is not True:
        raise Market05CanonicalExecutionNotAuthorized("MARKET_05_ARM_FLAG_MISMATCH")
    if payload.get("MARKET_05_EXECUTED") is not False:
        raise Market05CanonicalExecutionNotAuthorized("MARKET_05_ALREADY_EXECUTED")
    if payload.get("MARKET_05_OUTCOMES_INSPECTED") is not False:
        raise Market05CanonicalExecutionNotAuthorized("MARKET_05_OUTCOME_INSPECTED")
    if payload.get("authorization_consumed") is True:
        raise Market05CanonicalExecutionNotAuthorized("MARKET_05_ARM_CONSUMED")
    if int(payload.get("CANONICAL_EXECUTIONS_AUTHORIZED", 0)) != 1:
        raise Market05CanonicalExecutionNotAuthorized("MARKET_05_ARM_AUTHORIZED_MISMATCH")
    if int(payload.get("CANONICAL_EXECUTIONS_CONSUMED", 1)) != 0:
        raise Market05CanonicalExecutionNotAuthorized("MARKET_05_ARM_CONSUMED")

    return {
        "payload": payload,
        "sha256": sha256_file(_path(ARM_JSON_REL)),
        "run_identity": derived,
    }


def authenticate_market_05_reservation(*args: Any, **kwargs: Any) -> dict[str, Any]:
    """Durable one-shot state: AUTHORIZED=1 / CONSUMED=0 on disk."""
    _reject_caller_kwargs(args, kwargs)
    require_git_tracked_authority(RESERVATION_JSON_REL)
    payload = _load_json(RESERVATION_JSON_REL)

    if payload.get("research_id") != RESEARCH_ID:
        raise Market05CanonicalExecutionNotAuthorized(
            "MARKET_05_RESERVATION_RESEARCH_ID_MISMATCH"
        )
    derived = derive_market_05_run_identity()
    if payload.get("run_identity") != derived:
        raise Market05CanonicalExecutionNotAuthorized(
            "MARKET_05_RESERVATION_RUN_IDENTITY_MISMATCH"
        )
    if int(payload.get("CANONICAL_EXECUTIONS_AUTHORIZED", 0)) != 1:
        raise Market05CanonicalExecutionNotAuthorized(
            "MARKET_05_RESERVATION_AUTHORIZED_MISMATCH"
        )
    if int(payload.get("CANONICAL_EXECUTIONS_CONSUMED", 1)) != 0:
        raise Market05CanonicalExecutionNotAuthorized("MARKET_05_RESERVATION_CONSUMED")
    if payload.get("rerun_preauthorized") is True:
        raise Market05CanonicalExecutionNotAuthorized("MARKET_05_RERUN_PREAUTHORIZED")
    if payload.get("MARKET_05_EXECUTED") is not False:
        raise Market05CanonicalExecutionNotAuthorized("MARKET_05_ALREADY_EXECUTED")
    reject_protected_oos_authorization(payload)

    return {"payload": payload, "sha256": sha256_file(_path(RESERVATION_JSON_REL))}


def authenticate_market_05_canonical_execution(*args: Any, **kwargs: Any) -> dict[str, Any]:
    """Full authorization decision for exactly one canonical execution."""
    _reject_caller_kwargs(args, kwargs)
    arm = authenticate_market_05_arm()
    reservation = authenticate_market_05_reservation()
    if arm["payload"].get("run_identity") != reservation["payload"].get("run_identity"):
        raise Market05CanonicalExecutionNotAuthorized(
            "MARKET_05_ARM_RESERVATION_RUN_IDENTITY_DISAGREEMENT"
        )
    # RESULT must not already exist.
    for rel in (RESULT_JSON_REL, RESULT_MD_REL):
        if _path(rel).exists():
            raise Market05CanonicalExecutionNotAuthorized(
                "MARKET_05_RESULT_ALREADY_PRESENT"
            )
    return {
        "run_identity": arm["run_identity"],
        "arm": arm["payload"],
        "reservation": reservation["payload"],
        "arm_sha256": arm["sha256"],
        "reservation_sha256": reservation["sha256"],
    }


def market_05_execution_is_authorized() -> bool:
    """Non-raising predicate used by the frozen pre-ARM barrier."""
    try:
        authenticate_market_05_canonical_execution()
    except _refusal_exceptions():
        return False
    return True


def inspect_market_05_arm_state() -> dict[str, Any]:
    """Derive lifecycle state from artifacts. Never hardcoded."""
    try:
        arm = authenticate_market_05_arm()
        reservation = authenticate_market_05_reservation()
        authorized = int(reservation["payload"]["CANONICAL_EXECUTIONS_AUTHORIZED"])
        consumed = int(reservation["payload"]["CANONICAL_EXECUTIONS_CONSUMED"])
        return {
            "MARKET_05_ARMED": True,
            "IMPLEMENTATION_FROZEN": True,
            "MARKET_05_EXECUTION_AUTHORIZED": authorized == 1 and consumed == 0,
            "CANONICAL_EXECUTIONS_AUTHORIZED": authorized,
            "CANONICAL_EXECUTIONS_CONSUMED": consumed,
            "run_identity": arm["run_identity"],
            "MARKET_05_EXECUTED": bool(consumed),
            "MARKET_05_OUTCOME_INSPECTED": False,
            "MARKET_05_TEST_CALIBRATED": False,
            "PROTECTED_OOS_AUTHORIZED": False,
        }
    except _refusal_exceptions():
        return {
            "MARKET_05_ARMED": False,
            "IMPLEMENTATION_FROZEN": True,
            "MARKET_05_EXECUTION_AUTHORIZED": False,
            "CANONICAL_EXECUTIONS_AUTHORIZED": 0,
            "CANONICAL_EXECUTIONS_CONSUMED": 0,
            "run_identity": None,
            "MARKET_05_EXECUTED": False,
            "MARKET_05_OUTCOME_INSPECTED": False,
            "MARKET_05_TEST_CALIBRATED": False,
            "PROTECTED_OOS_AUTHORIZED": False,
        }


def consume_authorization_atomically(*args: Any, **kwargs: Any) -> dict[str, str]:
    """Durable single-use claim: 1/0 -> 1/1 written to disk.

    Re-authenticates first, so a crash/retry cannot produce two different
    scientific runs: once CONSUMED=1 is on disk, every later attempt fails
    authentication at MARKET_05_RESERVATION_CONSUMED.
    """
    _reject_caller_kwargs(args, kwargs)
    authenticate_market_05_canonical_execution()
    reservation_path = _path(RESERVATION_JSON_REL)
    arm_path = _path(ARM_JSON_REL)
    reservation = json.loads(reservation_path.read_text(encoding="utf-8"))
    arm = json.loads(arm_path.read_text(encoding="utf-8"))
    if int(reservation.get("CANONICAL_EXECUTIONS_CONSUMED", 1)) != 0:
        raise Market05CanonicalExecutionNotAuthorized("MARKET_05_RESERVATION_CONSUMED")
    if arm.get("authorization_consumed") is True:
        raise Market05CanonicalExecutionNotAuthorized("MARKET_05_ARM_CONSUMED")
    reservation["CANONICAL_EXECUTIONS_CONSUMED"] = 1
    reservation["MARKET_05_EXECUTED"] = True
    reservation["status"] = "CONSUMED"
    reservation["rerun_preauthorized"] = False
    arm["authorization_consumed"] = True
    arm["CANONICAL_EXECUTIONS_CONSUMED"] = 1
    arm["MARKET_05_EXECUTED"] = True
    arm["status"] = "EXECUTED"
    reservation_path.write_bytes(canonical_json_bytes(reservation))
    arm_path.write_bytes(canonical_json_bytes(arm))
    return {
        "reservation_sha256_consumed": sha256_file(reservation_path),
        "arm_sha256_consumed": sha256_file(arm_path),
        "CANONICAL_EXECUTIONS_AUTHORIZED": "1",
        "CANONICAL_EXECUTIONS_CONSUMED": "1",
    }
