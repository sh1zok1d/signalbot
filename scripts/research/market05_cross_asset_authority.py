"""MARKET-05 freeze authentication and fail-closed execution barrier.

Does not evaluate MARKET-05 outcomes. Does not load CORE BTC/ETH
scientific rows. Caller kwargs cannot substitute scientific authority.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


PREREG_MD_REL = "docs/research/MARKET_05_CROSS_ASSET_PREREG.md"
PREREG_JSON_REL = "docs/research/MARKET_05_CROSS_ASSET_PREREG.json"
IMPL_FREEZE_MD_REL = "docs/research/MARKET_05_IMPLEMENTATION_FREEZE.md"
IMPL_FREEZE_JSON_REL = "docs/research/MARKET_05_IMPLEMENTATION_FREEZE.json"
ARM_JSON_REL = "docs/research/MARKET_05_ARM.json"
ARM_MD_REL = "docs/research/MARKET_05_ARM.md"
RESULT_JSON_REL = "docs/research/MARKET_05_RESULT.json"
RESULT_MD_REL = "docs/research/MARKET_05_RESULT.md"
LIB_REL = "scripts/research/market05_cross_asset_lib.py"
AUTHORITY_REL = "scripts/research/market05_cross_asset_authority.py"
CLI_REL = "scripts/research/market05_cross_asset.py"
DATA_REL = "scripts/research/market05_cross_asset_data.py"
ETH_ACCEPTOR_LIB_REL = "scripts/research/core_eth_binance_v0_acceptor_lib.py"
ETH_INVENTORY_REL = "docs/research_data/CORE_ETH_BINANCE_V0/SOURCE_INVENTORY.json"
ETH_MANIFEST_REL = "docs/manifests/CORE_ETH_BINANCE_V0.yaml"

RESEARCH_ID = "MARKET-05_CROSS_ASSET_CONFIRMATION_ADVERSE_PATH_RISK"
FROZEN_PREREG_MD_SHA256 = (
    "31349f8863be3a79604d0c8dc93ca7037451ab16edb83a432d31af81f8a0193e"
)
FROZEN_PREREG_JSON_SHA256 = (
    "f2b2f6b98a3674412b584e6bd2686efa8fb9ce08b5d936e503e5d570a2428b25"
)
ETH_INVENTORY_SHA256 = (
    "033a06428d5d2a56fcde23a8fe64ebe4d8afa2f57d5d3263e3d0b9c6db38e49e"
)
BTC_DATASET_ID = "CORE_BTC_BINANCE_V0"
BTC_SNAPSHOT_ID = "717d37a404f81eefd58c9a796cc11868c48226baf1de8ffecad5e5607f8dd415"
ETH_DATASET_ID = "CORE_ETH_BINANCE_V0"
ETH_SNAPSHOT_ID = "4b9c113f659e1c1ca71498096dfdc2628a1016346aed40e19020efb64c85ad15"

MARKET_05_ARMED = False
MARKET_05_EXECUTION_AUTHORIZED = False
CANONICAL_EXECUTIONS_AUTHORIZED = 0
CANONICAL_EXECUTIONS_CONSUMED = 0
PROTECTED_OOS_AUTHORIZED = False
MARKET_05_TEST_CALIBRATED = False

ALLOWED_TEST_ORIGINS = frozenset({"synthetic", "handcrafted", "fixture"})


class Market05AuthorityError(RuntimeError):
    """Frozen-authority or identity failure."""


class Market05ExecutionNotAuthorized(RuntimeError):
    def __init__(self, message: str = "MARKET_05_EXECUTION_NOT_AUTHORIZED") -> None:
        super().__init__(message)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _path(rel: str) -> Path:
    return _repo_root() / rel


def _reject_caller_kwargs(args: tuple[Any, ...], kwargs: Mapping[str, Any]) -> None:
    if args or kwargs:
        raise Market05ExecutionNotAuthorized(
            "caller arguments cannot redefine MARKET-05 scientific authority"
        )


def authenticate_frozen_prereg_bytes(*args: Any, **kwargs: Any) -> dict[str, str]:
    _reject_caller_kwargs(args, kwargs)
    md = sha256_file(_path(PREREG_MD_REL))
    js = sha256_file(_path(PREREG_JSON_REL))
    if md != FROZEN_PREREG_MD_SHA256 or js != FROZEN_PREREG_JSON_SHA256:
        raise Market05AuthorityError("MARKET_05_PREREG_BYTE_IDENTITY_MISMATCH")
    return {"prereg_md_sha256": md, "prereg_json_sha256": js}


def load_accepted_eth_snapshot_id() -> str:
    manifest = _path(ETH_MANIFEST_REL).read_text(encoding="utf-8")
    if "status: ACCEPTED_FOR_DISCOVERY" not in manifest:
        raise Market05AuthorityError("CORE_ETH_NOT_ACCEPTED")
    snap = None
    for line in manifest.splitlines():
        if line.startswith("snapshot_id:"):
            snap = line.split(":", 1)[1].strip()
            break
    if not snap or snap != ETH_SNAPSHOT_ID:
        raise Market05AuthorityError("CORE_ETH_SNAPSHOT_ID_MISSING")
    inv = sha256_file(_path(ETH_INVENTORY_REL))
    if inv != ETH_INVENTORY_SHA256:
        raise Market05AuthorityError("CORE_ETH_INVENTORY_SHA256_MISMATCH")
    return snap


def refuse_bound_execution(reason: str = "MARKET_05_EXECUTION_NOT_AUTHORIZED") -> None:
    raise Market05ExecutionNotAuthorized(reason)


def refuse_unarmed_canonical_execution(*args: Any, **kwargs: Any) -> None:
    _reject_caller_kwargs(args, kwargs)
    if MARKET_05_EXECUTION_AUTHORIZED or MARKET_05_ARMED:
        raise Market05AuthorityError("MARKET_05_LIFECYCLE_FLAG_MUST_REMAIN_UNARMED")
    if _path(ARM_JSON_REL).exists() or _path(ARM_MD_REL).exists():
        raise Market05AuthorityError("MARKET_05_ARM_ARTIFACT_MUST_NOT_EXIST")
    refuse_bound_execution("MARKET_05_EXECUTION_NOT_AUTHORIZED")


def require_execution_authorized_before_outcome_load(*args: Any, **kwargs: Any) -> None:
    """Production scientific outcome load barrier.

    ARM does not exist in this unit, so this always fail-closes before any
    caller is allowed to read scientific outcome bars.
    """
    _reject_caller_kwargs(args, kwargs)
    if _path(ARM_JSON_REL).exists() or _path(ARM_MD_REL).exists():
        raise Market05AuthorityError("MARKET_05_ARM_ARTIFACT_MUST_NOT_EXIST")
    if MARKET_05_EXECUTION_AUTHORIZED or MARKET_05_ARMED:
        raise Market05AuthorityError("MARKET_05_LIFECYCLE_FLAG_MUST_REMAIN_UNARMED")
    raise Market05ExecutionNotAuthorized(
        "MARKET_05_EXECUTION_NOT_AUTHORIZED:outcome_load_refused_before_arm"
    )


def refuse_scientific_result_instantiation(*args: Any, **kwargs: Any) -> None:
    _reject_caller_kwargs(args, kwargs)
    if _path(RESULT_JSON_REL).exists() or _path(RESULT_MD_REL).exists():
        raise Market05AuthorityError("MARKET_05_RESULT_ARTIFACT_MUST_NOT_EXIST")
    raise Market05ExecutionNotAuthorized("MARKET_05_RESULT_INSTANTIATION_FORBIDDEN")


def inspect_market_05_authorization_state() -> dict[str, Any]:
    arm_exists = _path(ARM_JSON_REL).exists() or _path(ARM_MD_REL).exists()
    result_exists = _path(RESULT_JSON_REL).exists() or _path(RESULT_MD_REL).exists()
    return {
        "MARKET_05_ARMED": False,
        "MARKET_05_EXECUTION_AUTHORIZED": False,
        "CANONICAL_EXECUTIONS_AUTHORIZED": 0,
        "CANONICAL_EXECUTIONS_CONSUMED": 0,
        "arm_artifact_exists": arm_exists,
        "result_artifact_exists": result_exists,
        "run_identity": None,
        "MARKET_05_EXECUTED": False,
        "MARKET_05_OUTCOME_INSPECTED": False,
        "MARKET_05_TEST_CALIBRATED": False,
        "PROTECTED_OOS_AUTHORIZED": False,
    }


def origin_is_allowed_for_tests(origin: str | None) -> bool:
    return origin in ALLOWED_TEST_ORIGINS


def refuse_bound_scientific_inputs(
    *,
    origin: str | None,
    btc_snapshot_id: str | None = None,
    eth_snapshot_id: str | None = None,
    dataset_id: str | None = None,
) -> None:
    if MARKET_05_EXECUTION_AUTHORIZED:
        raise Market05AuthorityError("MARKET_05_BOUND_EXECUTION_FLAG_MUST_REMAIN_FALSE")
    if dataset_id in {BTC_DATASET_ID, ETH_DATASET_ID}:
        raise Market05ExecutionNotAuthorized("MARKET_05_BOUND_DATASET_REFUSED")
    if btc_snapshot_id == BTC_SNAPSHOT_ID:
        raise Market05ExecutionNotAuthorized("MARKET_05_BOUND_BTC_SNAPSHOT_REFUSED")
    if eth_snapshot_id is not None and eth_snapshot_id == ETH_SNAPSHOT_ID:
        raise Market05ExecutionNotAuthorized("MARKET_05_BOUND_ETH_SNAPSHOT_REFUSED")
    if eth_snapshot_id is not None:
        raise Market05ExecutionNotAuthorized("MARKET_05_BOUND_ETH_SNAPSHOT_REFUSED")
    if not origin_is_allowed_for_tests(origin):
        raise Market05ExecutionNotAuthorized(
            "MARKET_05_ORIGIN_NOT_AUTHORIZED_FOR_IMPLEMENTATION_UNIT"
        )
