"""MARKET-01 freeze/prereg authentication and one-shot ARM binding.

Does not evaluate MARKET outcomes. Does not load CORE/OI from disk.
Caller kwargs cannot substitute scientific authority.
"""

from __future__ import annotations

import hashlib
import inspect
import json
from pathlib import Path
from typing import Any, Mapping


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


PREREG_MD_REL = "docs/research/MARKET_01_OI_EXPANSION_WEAK_CONTINUATION_PREREG.md"
PREREG_JSON_REL = "docs/research/MARKET_01_OI_EXPANSION_WEAK_CONTINUATION_PREREG.json"
PREREG_FREEZE_MD_REL = (
    "docs/research/MARKET_01_OI_EXPANSION_WEAK_CONTINUATION_PREREG_FREEZE.md"
)
PREREG_FREEZE_JSON_REL = (
    "docs/research/MARKET_01_OI_EXPANSION_WEAK_CONTINUATION_PREREG_FREEZE.json"
)
IMPL_FREEZE_JSON_REL = (
    "docs/research/MARKET_01_OI_EXPANSION_WEAK_CONTINUATION_IMPLEMENTATION_FREEZE.json"
)
IMPL_FREEZE_MD_REL = (
    "docs/research/MARKET_01_OI_EXPANSION_WEAK_CONTINUATION_IMPLEMENTATION_FREEZE.md"
)
ARM_JSON_REL = "docs/research/MARKET_01_OI_EXPANSION_WEAK_CONTINUATION_ARM.json"
RESERVATION_JSON_REL = (
    "docs/research/MARKET_01_OI_EXPANSION_WEAK_CONTINUATION_RESERVATION.json"
)
LIB_REL = "scripts/research/market_01_oi_expansion_weak_continuation_lib.py"
B2_03_REL = "scripts/research/b2_03_impulse_morphology_lib.py"
V1_LIB_REL = "scripts/research/harness_synthetic_edge_calibration_v1_lib.py"
V3_CONFIRMATORY_REL = (
    "scripts/research/harness_synthetic_edge_calibration_v3_confirmatory.py"
)

RESEARCH_ID = "MARKET-01_OI_EXPANSION_WEAK_CONTINUATION"
FROZEN_PREREG_MD_SHA256 = "d82b60e1a923e8eb897252abc4a9013b6535357004f2dc7dc08f56f072542866"
FROZEN_PREREG_JSON_SHA256 = "6885abaf178401a1307e9adc5c02c69dac4fb5f3034bfddebfafc2439dde2ce4"
FROZEN_FREEZE_MD_SHA256 = "e0e0da9e22ebed9a9663e3c5f973237e3231e991f13227378288779e6ea07fe4"
FROZEN_FREEZE_JSON_SHA256 = "902863878acd2897c9dacdee6fae068ee17f87f6e10893d3c756b1f49b488176"
IMPL_FREEZE_JSON_SHA256 = "a057260f3002977142dec03438b03dad6e762bf53b3853374661c39f0bc77a91"
ARM_JSON_SHA256 = "5b639453030ae3d18efc40dc3ffffeeade0b152719cc38ba4cac660aecba75dd"
RESERVATION_JSON_SHA256 = "ebfa2cae43541c617540d19c879e9858b692c99c60563dc9aa206c9355455845"
FROZEN_MARKET_01_RUN_IDENTITY = (
    "f430399f46e6122a2633a34e99e9bd0ab8fe65c1baf9c05b5982551a4608739d"
)

ACCEPTED_IMPLEMENTATION_HEAD = "1019c5725a58c62d460276159a5683a202c1c3ea"
ACCEPTED_IMPLEMENTATION_TREE = "2a7a5ce74f9b0c419cf40093271df243ffb02d46"
PREREG_FREEZE_HEAD = "8fa0d361d137271754909034026f42d4dfdfc00a"
PREREG_FREEZE_TREE = "acde57e3cf4c17c9888016ff96928be2822e1866"

LIB_REVIEWED_SHA256 = "ad81bc279b381285e81deca6cd78bdd40673b203ea8aa8f8190b1507e33a424a"
LIB_ARMED_LIFECYCLE_SHA256 = (
    "9a8f46b39114558d38ae61600cb632fb963c7751d37e7699c4f155d91126dc09"
)
B2_03_SHA256 = "6da1e590f83edab09247b8d238e410ef7ce4333f4f20ef0d8d1ad205391eb6ce"
V1_LIB_SHA256 = "12230dcad714e3a06d3f57de69b78fedcab088be950af3d06f959366f01d6c51"
V3_SELECTOR_MODULE_SHA256 = (
    "38a494917dcf721b828a7c3f885d4c60ab6df437003abc0c71e510e33b4b0505"
)
SELECTOR_FUNCTION_SHA256 = (
    "66ed0ea015b773f8e469a470ddcd0e648806803249c93de14211ff6b8a4782b1"
)
ARCH_SOURCE_SHA256 = "104d3552a8e79a801e2f8cd0401160f83a7263b4ff13da44a82d763e5664fd21"
ARCH_PACKAGE_VERSION = "8.0.0"

PRICE_DATASET_ID = "CORE_BTC_BINANCE_V0"
PRICE_SNAPSHOT_ID = "717d37a404f81eefd58c9a796cc11868c48226baf1de8ffecad5e5607f8dd415"
OI_SNAPSHOT_ID = "5a9d036b23721d75b519b8478b81e333791227376d25cbeea5f0666c90730a33"
COMMON_START_INCLUSIVE = "2020-09-01T00:00:00Z"
COMMON_END_EXCLUSIVE = "2025-01-01T00:00:00Z"
SEED_MATERIAL = (
    "MARKET-01_OI_EXPANSION_WEAK_CONTINUATION|CONFIRMATORY_STATIONARY_BOOTSTRAP|B=999"
)
SEED_MATERIAL_SHA256 = "a960350293eacee83f5cfcb21e138f5f4dbbea1af4547d298e5a1da2ec571dbe"
MARKET_01_BOOTSTRAP_SEED = 12204813275361890024

MARKET_01_TEST_CALIBRATED = False
B2_06_EXECUTION_AUTHORIZED = False
DEFAULT_V4 = False
PROTECTED_OOS_AUTHORIZED = False

CANONICAL_EXECUTIONS_AUTHORIZED = 1
ARM_OUTCOME_FIELDS = (
    "reversal_return",
    "beta_candidate",
    "p_one_sided",
    "final_classification",
    "CANDIDATE_EPISODES",
    "candidate_count",
    "outcome_return",
)


class Market01AuthorityError(RuntimeError):
    """Frozen-authority or identity failure."""


class Market01ExecutionNotAuthorized(RuntimeError):
    def __init__(self, message: str = "MARKET_01_EXECUTION_NOT_AUTHORIZED") -> None:
        super().__init__(message)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_json_bytes(payload: Mapping[str, Any]) -> bytes:
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
        raise Market01ExecutionNotAuthorized(
            "caller arguments cannot redefine MARKET-01 scientific authority"
        )


def _path(rel: str) -> Path:
    return _repo_root() / rel


def _load_json(rel: str) -> dict[str, Any]:
    return json.loads(_path(rel).read_text(encoding="utf-8"))


def _require_file_sha256(rel: str, expected: str) -> str:
    digest = sha256_file(_path(rel))
    if digest != expected:
        raise Market01AuthorityError(f"MARKET_01_BYTE_IDENTITY_MISMATCH:{rel}")
    return digest


def authenticate_frozen_prereg_bytes(*args: Any, **kwargs: Any) -> None:
    _reject_caller_kwargs(args, kwargs)
    md = sha256_file(_path(PREREG_MD_REL))
    js = sha256_file(_path(PREREG_JSON_REL))
    if md != FROZEN_PREREG_MD_SHA256 or js != FROZEN_PREREG_JSON_SHA256:
        raise Market01AuthorityError("MARKET_01_PREREG_BYTE_IDENTITY_MISMATCH")
    freeze_md = sha256_file(_path(PREREG_FREEZE_MD_REL))
    freeze_js = sha256_file(_path(PREREG_FREEZE_JSON_REL))
    if freeze_md != FROZEN_FREEZE_MD_SHA256 or freeze_js != FROZEN_FREEZE_JSON_SHA256:
        raise Market01AuthorityError("MARKET_01_FREEZE_BYTE_IDENTITY_MISMATCH")


def authenticate_arch_selector(*args: Any, **kwargs: Any) -> dict:
    _reject_caller_kwargs(args, kwargs)
    try:
        import arch
        import arch.bootstrap.base as base
    except ImportError as exc:
        raise Market01AuthorityError("MARKET_01_ARCH_SELECTOR_UNAVAILABLE") from exc
    version = str(getattr(arch, "__version__", ""))
    if version != ARCH_PACKAGE_VERSION:
        raise Market01AuthorityError(
            f"MARKET_01_ARCH_VERSION_MISMATCH:{version!r}"
        )
    path = Path(base.__file__)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != ARCH_SOURCE_SHA256:
        raise Market01AuthorityError("MARKET_01_ARCH_SOURCE_SHA256_MISMATCH")
    return {
        "package": "arch",
        "package_version": version,
        "source_file": "arch/bootstrap/base.py",
        "source_file_sha256": digest,
        "branch": "stationary-bootstrap only (c=2, b_sb)",
    }


def refuse_bound_execution() -> None:
    raise Market01ExecutionNotAuthorized()


def snapshot_is_bound(snapshot_id: str | None) -> bool:
    if snapshot_id is None:
        return False
    return snapshot_id in {PRICE_SNAPSHOT_ID, OI_SNAPSHOT_ID}


def authenticate_market_01_implementation_bytes(*args: Any, **kwargs: Any) -> None:
    _reject_caller_kwargs(args, kwargs)
    _require_file_sha256(LIB_REL, LIB_ARMED_LIFECYCLE_SHA256)
    _require_file_sha256(B2_03_REL, B2_03_SHA256)
    _require_file_sha256(V1_LIB_REL, V1_LIB_SHA256)
    _require_file_sha256(V3_CONFIRMATORY_REL, V3_SELECTOR_MODULE_SHA256)
    from scripts.research.harness_synthetic_edge_calibration_v3_confirmatory import (
        optimal_stationary_block_length,
    )

    fn_digest = _sha256_bytes(
        inspect.getsource(optimal_stationary_block_length).encode("utf-8")
    )
    if fn_digest != SELECTOR_FUNCTION_SHA256:
        raise Market01AuthorityError("MARKET_01_SELECTOR_FUNCTION_MISMATCH")


def _scientific_run_identity_payload() -> dict[str, Any]:
    return {
        "schema": "market_01_oi_expansion_weak_continuation_scientific_run_identity",
        "schema_version": "1.0.0",
        "research_id": RESEARCH_ID,
        "purpose": "CANONICAL_MARKET_01_EXECUTION",
        "implementation_review_verdict": "IMPLEMENTATION_ACCEPTED",
        "prereg_md_sha256": FROZEN_PREREG_MD_SHA256,
        "prereg_json_sha256": FROZEN_PREREG_JSON_SHA256,
        "prereg_freeze_md_sha256": FROZEN_FREEZE_MD_SHA256,
        "prereg_freeze_json_sha256": FROZEN_FREEZE_JSON_SHA256,
        "prereg_freeze_head": PREREG_FREEZE_HEAD,
        "prereg_freeze_tree": PREREG_FREEZE_TREE,
        "accepted_implementation_head": ACCEPTED_IMPLEMENTATION_HEAD,
        "accepted_implementation_tree": ACCEPTED_IMPLEMENTATION_TREE,
        "implementation_freeze_json_sha256": IMPL_FREEZE_JSON_SHA256,
        "files": {
            "lib_reviewed_sha256": LIB_REVIEWED_SHA256,
            "lib_armed_lifecycle_sha256": LIB_ARMED_LIFECYCLE_SHA256,
            "b2_03_sha256": B2_03_SHA256,
            "v1_lib_sha256": V1_LIB_SHA256,
            "v3_selector_module_sha256": V3_SELECTOR_MODULE_SHA256,
            "selector_function_sha256": SELECTOR_FUNCTION_SHA256,
            "arch_source_sha256": ARCH_SOURCE_SHA256,
        },
        "data": {
            "price_dataset_id": PRICE_DATASET_ID,
            "price_snapshot_id": PRICE_SNAPSHOT_ID,
            "oi_source": "Binance Vision daily/metrics/BTCUSDT",
            "oi_field": "sum_open_interest",
            "oi_snapshot_id": OI_SNAPSHOT_ID,
            "common_start_inclusive": COMMON_START_INCLUSIVE,
            "common_end_exclusive": COMMON_END_EXCLUSIVE,
        },
        "bootstrap": {
            "seed_material": SEED_MATERIAL,
            "seed_material_sha256": SEED_MATERIAL_SHA256,
            "MARKET_01_BOOTSTRAP_SEED": MARKET_01_BOOTSTRAP_SEED,
            "B": 999,
            "alpha": 0.05,
        },
        "MARKET_01_TEST_CALIBRATED": False,
        "v3_reused_as_market_01_test": False,
        "default_v4": False,
        "b2_06_execution_authorized": False,
        "protected_oos_authorized": False,
        "funding_in_scope": False,
    }


def derive_market_01_run_identity(*args: Any, **kwargs: Any) -> str:
    _reject_caller_kwargs(args, kwargs)
    return _sha256_bytes(canonical_json_bytes(_scientific_run_identity_payload()))


def authenticate_market_01_implementation_freeze(*args: Any, **kwargs: Any) -> dict[str, Any]:
    _reject_caller_kwargs(args, kwargs)
    try:
        payload = _load_json(IMPL_FREEZE_JSON_REL)
        digest = sha256_file(_path(IMPL_FREEZE_JSON_REL))
    except OSError as exc:
        raise Market01ExecutionNotAuthorized("MARKET_01_IMPLEMENTATION_FREEZE_MISSING") from exc
    if digest != IMPL_FREEZE_JSON_SHA256:
        raise Market01AuthorityError(f"MARKET_01_BYTE_IDENTITY_MISMATCH:{IMPL_FREEZE_JSON_REL}")
    if payload.get("research_id") != RESEARCH_ID:
        raise Market01AuthorityError("MARKET_01_IMPLEMENTATION_FREEZE_IDENTITY_MISMATCH")
    reviewed = payload.get("reviewed_implementation") or {}
    if reviewed.get("head") != ACCEPTED_IMPLEMENTATION_HEAD:
        raise Market01AuthorityError("MARKET_01_REVIEWED_HEAD_MISMATCH")
    if reviewed.get("tree") != ACCEPTED_IMPLEMENTATION_TREE:
        raise Market01AuthorityError("MARKET_01_REVIEWED_TREE_MISMATCH")
    data = payload.get("data_authority") or {}
    if data.get("price_snapshot_id") != PRICE_SNAPSHOT_ID:
        raise Market01AuthorityError("MARKET_01_PRICE_SNAPSHOT_MISMATCH")
    if data.get("oi_snapshot_id") != OI_SNAPSHOT_ID:
        raise Market01AuthorityError("MARKET_01_OI_SNAPSHOT_MISMATCH")
    return {"payload": payload, "sha256": digest}


def authenticate_market_01_arm(*args: Any, **kwargs: Any) -> dict[str, Any]:
    _reject_caller_kwargs(args, kwargs)
    authenticate_frozen_prereg_bytes()
    authenticate_market_01_implementation_freeze()
    authenticate_market_01_implementation_bytes()
    try:
        payload = _load_json(ARM_JSON_REL)
        digest = sha256_file(_path(ARM_JSON_REL))
    except OSError as exc:
        raise Market01ExecutionNotAuthorized("MARKET_01_ARM_MISSING") from exc
    for field in ARM_OUTCOME_FIELDS:
        if field in payload:
            raise Market01AuthorityError("MARKET_01_ARM_CONTAINS_OUTCOME_FIELD")
    if payload.get("freeze_artifact_sha256") != IMPL_FREEZE_JSON_SHA256:
        raise Market01ExecutionNotAuthorized("MARKET_01_ARM_IDENTITY_MISMATCH")
    if payload.get("run_identity") != FROZEN_MARKET_01_RUN_IDENTITY:
        raise Market01ExecutionNotAuthorized("MARKET_01_ARM_RUN_IDENTITY_MISMATCH")
    derived = derive_market_01_run_identity()
    if payload.get("run_identity") != derived:
        raise Market01ExecutionNotAuthorized("MARKET_01_ARM_RUN_IDENTITY_MISMATCH")
    if payload.get("reviewed_implementation_head") != ACCEPTED_IMPLEMENTATION_HEAD:
        raise Market01ExecutionNotAuthorized("MARKET_01_ARM_IMPLEMENTATION_MISMATCH")
    if payload.get("reviewed_implementation_tree") != ACCEPTED_IMPLEMENTATION_TREE:
        raise Market01ExecutionNotAuthorized("MARKET_01_ARM_IMPLEMENTATION_MISMATCH")
    if payload.get("lib_armed_lifecycle_sha256") != LIB_ARMED_LIFECYCLE_SHA256:
        raise Market01ExecutionNotAuthorized("MARKET_01_ARM_IMPLEMENTATION_MISMATCH")
    if payload.get("price_snapshot_id") != PRICE_SNAPSHOT_ID:
        raise Market01ExecutionNotAuthorized("MARKET_01_ARM_SNAPSHOT_MISMATCH")
    if payload.get("oi_snapshot_id") != OI_SNAPSHOT_ID:
        raise Market01ExecutionNotAuthorized("MARKET_01_ARM_SNAPSHOT_MISMATCH")
    if payload.get("authorization_consumed") is True:
        raise Market01ExecutionNotAuthorized("MARKET_01_ARM_CONSUMED")
    if int(payload.get("authorized_run_count", 0)) != 1:
        raise Market01ExecutionNotAuthorized("MARKET_01_ARM_RUN_COUNT_MISMATCH")
    if payload.get("MARKET_01_TEST_CALIBRATED") is not False:
        raise Market01AuthorityError("MARKET_01_TEST_CALIBRATED_MUTATED")
    if payload.get("DEFAULT_V4") is not False:
        raise Market01AuthorityError("MARKET_01_DEFAULT_V4_MUTATED")
    if payload.get("B2_06_EXECUTION_AUTHORIZED") is not False:
        raise Market01AuthorityError("MARKET_01_B2_06_MUTATED")
    if payload.get("v3_reused_as_market_01_test") is not False:
        raise Market01AuthorityError("MARKET_01_V3_CONTAMINATION")
    if digest != ARM_JSON_SHA256:
        raise Market01AuthorityError(f"MARKET_01_BYTE_IDENTITY_MISMATCH:{ARM_JSON_REL}")
    return {"payload": payload, "sha256": digest, "run_identity": derived}


def authenticate_market_01_reservation(*args: Any, **kwargs: Any) -> dict[str, Any]:
    _reject_caller_kwargs(args, kwargs)
    try:
        payload = _load_json(RESERVATION_JSON_REL)
        digest = sha256_file(_path(RESERVATION_JSON_REL))
    except OSError as exc:
        raise Market01ExecutionNotAuthorized("MARKET_01_RESERVATION_MISSING") from exc
    if payload.get("run_identity") != FROZEN_MARKET_01_RUN_IDENTITY:
        raise Market01ExecutionNotAuthorized("MARKET_01_RESERVATION_RUN_IDENTITY_MISMATCH")
    if payload.get("arm_artifact_sha256") != ARM_JSON_SHA256:
        raise Market01ExecutionNotAuthorized("MARKET_01_RESERVATION_ARM_MISMATCH")
    if int(payload.get("CANONICAL_EXECUTIONS_AUTHORIZED", 0)) != 1:
        raise Market01ExecutionNotAuthorized("MARKET_01_RESERVATION_AUTHORIZED_MISMATCH")
    if int(payload.get("CANONICAL_EXECUTIONS_CONSUMED", 1)) != 0:
        raise Market01ExecutionNotAuthorized("MARKET_01_RESERVATION_CONSUMED")
    if payload.get("rerun_preauthorized") is True:
        raise Market01ExecutionNotAuthorized("MARKET_01_RERUN_PREAUTHORIZED")
    if payload.get("MARKET_01_EXECUTED") is not False:
        raise Market01ExecutionNotAuthorized("MARKET_01_ALREADY_EXECUTED")
    if payload.get("MARKET_01_OUTCOME_INSPECTED") is not False:
        raise Market01ExecutionNotAuthorized("MARKET_01_OUTCOME_INSPECTED")
    if digest != RESERVATION_JSON_SHA256:
        raise Market01AuthorityError(
            f"MARKET_01_BYTE_IDENTITY_MISMATCH:{RESERVATION_JSON_REL}"
        )
    return {"payload": payload, "sha256": digest}


def authenticate_market_01_canonical_execution(*args: Any, **kwargs: Any) -> dict[str, Any]:
    _reject_caller_kwargs(args, kwargs)
    arm = authenticate_market_01_arm()
    reservation = authenticate_market_01_reservation()
    authenticate_arch_selector()
    return {
        "run_identity": arm["run_identity"],
        "arm": arm["payload"],
        "reservation": reservation["payload"],
    }


def authorize_bound_market_01_views(
    price_snapshot_id: str | None,
    oi_snapshot_id: str | None,
    *args: Any,
    **kwargs: Any,
) -> dict[str, Any]:
    _reject_caller_kwargs(args, kwargs)
    if price_snapshot_id != PRICE_SNAPSHOT_ID or oi_snapshot_id != OI_SNAPSHOT_ID:
        raise Market01ExecutionNotAuthorized("MARKET_01_SNAPSHOT_IDENTITY_MISMATCH")
    try:
        return authenticate_market_01_canonical_execution()
    except Market01AuthorityError as exc:
        raise Market01ExecutionNotAuthorized(str(exc)) from exc


def inspect_market_01_authorization_state() -> dict[str, Any]:
    try:
        arm = authenticate_market_01_arm()
        reservation = authenticate_market_01_reservation()
        consumed = int(reservation["payload"]["CANONICAL_EXECUTIONS_CONSUMED"])
        authorized = int(reservation["payload"]["CANONICAL_EXECUTIONS_AUTHORIZED"])
        return {
            "MARKET_01_ARMED": True,
            "MARKET_01_EXECUTION_AUTHORIZED": consumed == 0 and authorized == 1,
            "CANONICAL_EXECUTIONS_AUTHORIZED": authorized,
            "CANONICAL_EXECUTIONS_CONSUMED": consumed,
            "run_identity": arm["run_identity"],
            "MARKET_01_EXECUTED": False,
            "MARKET_01_OUTCOME_INSPECTED": False,
            "MARKET_01_TEST_CALIBRATED": False,
        }
    except (Market01AuthorityError, Market01ExecutionNotAuthorized, OSError, json.JSONDecodeError):
        return {
            "MARKET_01_ARMED": False,
            "MARKET_01_EXECUTION_AUTHORIZED": False,
            "CANONICAL_EXECUTIONS_AUTHORIZED": 0,
            "CANONICAL_EXECUTIONS_CONSUMED": 0,
            "run_identity": None,
            "MARKET_01_EXECUTED": False,
            "MARKET_01_OUTCOME_INSPECTED": False,
            "MARKET_01_TEST_CALIBRATED": False,
        }
