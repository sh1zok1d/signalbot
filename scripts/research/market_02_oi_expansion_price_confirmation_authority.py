"""MARKET-02 freeze/prereg authentication and one-shot ARM binding.

Does not evaluate MARKET-02 outcomes. Does not load CORE/OI from disk.
Does not open protected 2025/2026 OOS contents. Caller kwargs cannot
substitute scientific authority.
"""

from __future__ import annotations

import hashlib
import inspect
import json
from pathlib import Path
from typing import Any, Mapping


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


PREREG_MD_REL = "docs/research/MARKET_02_OI_EXPANSION_PRICE_CONFIRMATION_PREREG.md"
PREREG_JSON_REL = "docs/research/MARKET_02_OI_EXPANSION_PRICE_CONFIRMATION_PREREG.json"
IMPL_FREEZE_JSON_REL = (
    "docs/research/MARKET_02_OI_EXPANSION_PRICE_CONFIRMATION_IMPLEMENTATION_FREEZE.json"
)
IMPL_FREEZE_MD_REL = (
    "docs/research/MARKET_02_OI_EXPANSION_PRICE_CONFIRMATION_IMPLEMENTATION_FREEZE.md"
)
ARM_JSON_REL = "docs/research/MARKET_02_OI_EXPANSION_PRICE_CONFIRMATION_ARM.json"
ARM_MD_REL = "docs/research/MARKET_02_OI_EXPANSION_PRICE_CONFIRMATION_ARM.md"
RESERVATION_JSON_REL = (
    "docs/research/MARKET_02_OI_EXPANSION_PRICE_CONFIRMATION_RESERVATION.json"
)
RESULT_JSON_REL = "docs/research/MARKET_02_OI_EXPANSION_PRICE_CONFIRMATION_RESULT.json"
LIB_REL = "scripts/research/market_02_oi_expansion_price_confirmation_lib.py"
FAST_PRECOMPUTE_REL = "scripts/research/market_01_episode_construction_fast.py"
M01_LIB_REL = "scripts/research/market_01_oi_expansion_weak_continuation_lib.py"
B2_03_REL = "scripts/research/b2_03_impulse_morphology_lib.py"
V1_LIB_REL = "scripts/research/harness_synthetic_edge_calibration_v1_lib.py"
V3_CONFIRMATORY_REL = (
    "scripts/research/harness_synthetic_edge_calibration_v3_confirmatory.py"
)
CORE_SNAPSHOT_IDENTITY_REL = (
    "docs/research_data/CORE_BTC_BINANCE_V0/SNAPSHOT_717d37a4.json"
)
CORE_MANIFEST_REL = "docs/manifests/CORE_BTC_BINANCE_V0.yaml"
OI_SNAPSHOT_IDENTITY_REL = (
    "docs/research_data/B2_06_BINANCE_UM_BTCUSDT_OI_FUNDING_V0/SNAPSHOT_5a9d036b.json"
)
OI_MANIFEST_REL = "docs/manifests/B2_06_BINANCE_UM_BTCUSDT_OI_FUNDING_V0.yaml"

RESEARCH_ID = "MARKET-02_OI_EXPANSION_PRICE_CONFIRMATION"
FROZEN_PREREG_MD_SHA256 = "4f19fd27435adddf4cc7e3c5568a8e316d8865b64468cdc30a9fd3918ffc3275"
FROZEN_PREREG_JSON_SHA256 = "ffc11ffd0f9d76ca12542ce45f466a6a7f9c651f1a030168a1617af2caa545a7"
IMPL_FREEZE_JSON_SHA256 = "204da4872393461185f568ce46552cd9c4893b1f04db3264ba671cdf153d06fb"
IMPL_FREEZE_JSON_SIZE = 10329
IMPL_FREEZE_MD_SHA256 = "684f86733e49a90ca13ace3cebfcfccb51d7422d6b9fa0f121643e934e50970e"

REVIEWED_IMPLEMENTATION_HEAD = "1d2b0abf73d245f37cd9ca55ece99d1628dc80ee"
REVIEWED_IMPLEMENTATION_TREE = "9e18ccf690e280bbd4b033f4a44f3b0700a5bedb"
FROZEN_IMPLEMENTATION_HEAD = "124da2bfdb0b5dfb6e0a8da5789a474af526f27f"
FROZEN_IMPLEMENTATION_TREE = "7303a4507cba716209ea012f2c4e180eef31ba18"

LIB_REVIEWED_SHA256 = "51638796db235a999bd1a12d44a57aace9e21f4b0cfffeea14bdabaf3eac7ea6"
LIB_REVIEWED_SIZE = 38441
LIB_ARMED_LIFECYCLE_SHA256 = (
    "8fa923329da9027a0a8733a0483c1edd3e266ef56e2f8dee07cb5a1601aacbe3"
)
LIB_ARMED_LIFECYCLE_SIZE = 39267
FAST_PRECOMPUTE_SHA256 = "ddcabb999c2ea033a674ee84a484333802d3f863ab012c6784eb1784af2640ef"
M01_LIB_SHA256 = "9a8f46b39114558d38ae61600cb632fb963c7751d37e7699c4f155d91126dc09"
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
OI_DATASET_ID = "B2_06_BINANCE_UM_BTCUSDT_OI_FUNDING_V0"
OI_SNAPSHOT_ID = "5a9d036b23721d75b519b8478b81e333791227376d25cbeea5f0666c90730a33"
COMMON_START_INCLUSIVE = "2020-09-01T00:00:00Z"
COMMON_END_EXCLUSIVE = "2025-01-01T00:00:00Z"
CORE_DATASET_START_INCLUSIVE = "2020-01-01T00:00:00Z"
CORE_DATASET_END_EXCLUSIVE = "2026-08-26T00:00:00Z"

CORE_SNAPSHOT_IDENTITY_SHA256 = (
    "a104a4036ed7b4c7a4a9954ce1aeee247b6bbbb91d6abf2563b78b6bd9f84630"
)
CORE_SNAPSHOT_IDENTITY_SIZE = 74422
CORE_MANIFEST_SHA256 = "efd6920fa4966c0d3a7aa00fe0266d05d56182bf235f6f258730029c498c401e"
CORE_MANIFEST_SIZE = 10243
OI_SNAPSHOT_IDENTITY_SHA256 = (
    "bb216f9abdb9fcd7c7648bbffb8541e811af06498d062faa5f31037793768e5e"
)
OI_SNAPSHOT_IDENTITY_SIZE = 1863449
OI_MANIFEST_SHA256 = "53237cedd27e3a0fc25137776149a1db4c58a61d462f07876681afbd3cc9c141"
OI_MANIFEST_SIZE = 3584

SEED_MATERIAL = (
    "MARKET-02_OI_EXPANSION_PRICE_CONFIRMATION|CONFIRMATORY_STATIONARY_BOOTSTRAP|B=999"
)
SEED_MATERIAL_SHA256 = "19b71ee831e69f273338ef94e65ff4cc339eb6d8054c365fd160c7769955558f"
MARKET_02_BOOTSTRAP_SEED = "1852983754304692007"
JSON_TWIN_STORED_NUMERIC = "1852983754304692000"

MARKET_02_TEST_CALIBRATED = False
B2_06_EXECUTION_AUTHORIZED = False
DEFAULT_V4 = False
PROTECTED_OOS_AUTHORIZED = False
V3_REUSED_AS_MARKET_02_TEST = False
FUNDING_IN_SCOPE = False

CANONICAL_EXECUTIONS_AUTHORIZED = 1
ARM_JSON_SHA256 = "4cbb2212f4bf6ba2ded8d109d437434b79c24e436473acf9c771d80cd84542ae"
RESERVATION_JSON_SHA256 = (
    "ca0eb13a0a0559c9227e4b99be0491b3845bb03566426d4e01da68cbc21c59c1"
)
FROZEN_MARKET_02_RUN_IDENTITY = (
    "4ef6a6c543f6a11930fe0ae26cb6bfbe7f19feac4c645d8fed992eebcd36a032"
)

ARM_OUTCOME_FIELDS = (
    "continuation_return",
    "beta_confirmation",
    "p_one_sided",
    "final_classification",
    "CANDIDATE_EPISODES",
    "BASELINE_EPISODES",
    "candidate_count",
    "baseline_count",
    "outcome_return",
    "detected",
    "robustness",
)


class Market02AuthorityError(RuntimeError):
    """Frozen-authority or identity failure."""


class Market02ExecutionNotAuthorized(RuntimeError):
    def __init__(self, message: str = "MARKET_02_EXECUTION_NOT_AUTHORIZED") -> None:
        super().__init__(message)


class Market02NotArmed(Market02ExecutionNotAuthorized):
    def __init__(self, message: str = "MARKET_02_NOT_ARMED") -> None:
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
        raise Market02ExecutionNotAuthorized(
            "caller arguments cannot redefine MARKET-02 scientific authority"
        )


def _path(rel: str) -> Path:
    return _repo_root() / rel


def _load_json(rel: str) -> dict[str, Any]:
    return json.loads(_path(rel).read_text(encoding="utf-8"))


def _require_file_sha256(rel: str, expected: str) -> str:
    digest = sha256_file(_path(rel))
    if digest != expected:
        raise Market02AuthorityError(f"MARKET_02_BYTE_IDENTITY_MISMATCH:{rel}")
    return digest


def refuse_bound_execution() -> None:
    raise Market02ExecutionNotAuthorized()


def snapshot_is_bound(snapshot_id: str | None) -> bool:
    if snapshot_id is None:
        return False
    return snapshot_id in {PRICE_SNAPSHOT_ID, OI_SNAPSHOT_ID}


def authenticate_frozen_prereg_bytes(*args: Any, **kwargs: Any) -> None:
    _reject_caller_kwargs(args, kwargs)
    md = sha256_file(_path(PREREG_MD_REL))
    js = sha256_file(_path(PREREG_JSON_REL))
    if md != FROZEN_PREREG_MD_SHA256 or js != FROZEN_PREREG_JSON_SHA256:
        raise Market02AuthorityError("MARKET_02_PREREG_BYTE_IDENTITY_MISMATCH")


def authenticate_arch_selector(*args: Any, **kwargs: Any) -> dict:
    _reject_caller_kwargs(args, kwargs)
    try:
        import arch
        import arch.bootstrap.base as base
    except ImportError as exc:
        raise Market02AuthorityError("MARKET_02_ARCH_SELECTOR_UNAVAILABLE") from exc
    version = str(getattr(arch, "__version__", ""))
    if version != ARCH_PACKAGE_VERSION:
        raise Market02AuthorityError(
            f"MARKET_02_ARCH_VERSION_MISMATCH:{version!r}"
        )
    path = Path(base.__file__)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != ARCH_SOURCE_SHA256:
        raise Market02AuthorityError("MARKET_02_ARCH_SOURCE_SHA256_MISMATCH")
    return {
        "package": "arch",
        "package_version": version,
        "source_file": "arch/bootstrap/base.py",
        "source_file_sha256": digest,
        "branch": "stationary-bootstrap only (c=2, b_sb)",
    }


def authenticate_market_02_implementation_bytes(*args: Any, **kwargs: Any) -> None:
    _reject_caller_kwargs(args, kwargs)
    _require_file_sha256(LIB_REL, LIB_ARMED_LIFECYCLE_SHA256)
    lib_size = _path(LIB_REL).stat().st_size
    if lib_size != LIB_ARMED_LIFECYCLE_SIZE:
        raise Market02AuthorityError("MARKET_02_LIB_SIZE_MISMATCH")
    _require_file_sha256(FAST_PRECOMPUTE_REL, FAST_PRECOMPUTE_SHA256)
    _require_file_sha256(M01_LIB_REL, M01_LIB_SHA256)
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
        raise Market02AuthorityError("MARKET_02_SELECTOR_FUNCTION_MISMATCH")


def authenticate_bound_input_identities(*args: Any, **kwargs: Any) -> None:
    _reject_caller_kwargs(args, kwargs)
    _require_file_sha256(CORE_SNAPSHOT_IDENTITY_REL, CORE_SNAPSHOT_IDENTITY_SHA256)
    if _path(CORE_SNAPSHOT_IDENTITY_REL).stat().st_size != CORE_SNAPSHOT_IDENTITY_SIZE:
        raise Market02AuthorityError("MARKET_02_CORE_SNAPSHOT_IDENTITY_SIZE_MISMATCH")
    _require_file_sha256(CORE_MANIFEST_REL, CORE_MANIFEST_SHA256)
    if _path(CORE_MANIFEST_REL).stat().st_size != CORE_MANIFEST_SIZE:
        raise Market02AuthorityError("MARKET_02_CORE_MANIFEST_SIZE_MISMATCH")
    _require_file_sha256(OI_SNAPSHOT_IDENTITY_REL, OI_SNAPSHOT_IDENTITY_SHA256)
    if _path(OI_SNAPSHOT_IDENTITY_REL).stat().st_size != OI_SNAPSHOT_IDENTITY_SIZE:
        raise Market02AuthorityError("MARKET_02_OI_SNAPSHOT_IDENTITY_SIZE_MISMATCH")
    _require_file_sha256(OI_MANIFEST_REL, OI_MANIFEST_SHA256)
    if _path(OI_MANIFEST_REL).stat().st_size != OI_MANIFEST_SIZE:
        raise Market02AuthorityError("MARKET_02_OI_MANIFEST_SIZE_MISMATCH")


def _scientific_run_identity_payload() -> dict[str, Any]:
    return {
        "schema": "market_02_oi_expansion_price_confirmation_scientific_run_identity",
        "schema_version": "1.0.0",
        "research_id": RESEARCH_ID,
        "purpose": "CANONICAL_MARKET_02_EXECUTION",
        "implementation_review_verdict": "READY_FOR_IMPLEMENTATION_FREEZE",
        "prereg_md_sha256": FROZEN_PREREG_MD_SHA256,
        "prereg_json_sha256": FROZEN_PREREG_JSON_SHA256,
        "reviewed_implementation_head": REVIEWED_IMPLEMENTATION_HEAD,
        "reviewed_implementation_tree": REVIEWED_IMPLEMENTATION_TREE,
        "frozen_implementation_head": FROZEN_IMPLEMENTATION_HEAD,
        "frozen_implementation_tree": FROZEN_IMPLEMENTATION_TREE,
        "implementation_freeze_json_sha256": IMPL_FREEZE_JSON_SHA256,
        "files": {
            "lib_reviewed_sha256": LIB_REVIEWED_SHA256,
            "lib_armed_lifecycle_sha256": LIB_ARMED_LIFECYCLE_SHA256,
            "fast_precompute_sha256": FAST_PRECOMPUTE_SHA256,
            "m01_lib_sha256": M01_LIB_SHA256,
            "b2_03_sha256": B2_03_SHA256,
            "v1_lib_sha256": V1_LIB_SHA256,
            "v3_selector_module_sha256": V3_SELECTOR_MODULE_SHA256,
            "selector_function_sha256": SELECTOR_FUNCTION_SHA256,
            "arch_source_sha256": ARCH_SOURCE_SHA256,
        },
        "data": {
            "price_dataset_id": PRICE_DATASET_ID,
            "price_snapshot_id": PRICE_SNAPSHOT_ID,
            "price_identity_path": CORE_SNAPSHOT_IDENTITY_REL,
            "price_identity_sha256": CORE_SNAPSHOT_IDENTITY_SHA256,
            "price_identity_size_bytes": CORE_SNAPSHOT_IDENTITY_SIZE,
            "price_manifest_path": CORE_MANIFEST_REL,
            "price_manifest_sha256": CORE_MANIFEST_SHA256,
            "price_manifest_size_bytes": CORE_MANIFEST_SIZE,
            "oi_dataset_id": OI_DATASET_ID,
            "oi_source": "Binance Vision daily/metrics/BTCUSDT",
            "oi_field": "sum_open_interest",
            "oi_snapshot_id": OI_SNAPSHOT_ID,
            "oi_identity_path": OI_SNAPSHOT_IDENTITY_REL,
            "oi_identity_sha256": OI_SNAPSHOT_IDENTITY_SHA256,
            "oi_identity_size_bytes": OI_SNAPSHOT_IDENTITY_SIZE,
            "oi_manifest_path": OI_MANIFEST_REL,
            "oi_manifest_sha256": OI_MANIFEST_SHA256,
            "oi_manifest_size_bytes": OI_MANIFEST_SIZE,
            "common_start_inclusive": COMMON_START_INCLUSIVE,
            "common_end_exclusive": COMMON_END_EXCLUSIVE,
            "core_dataset_start_inclusive": CORE_DATASET_START_INCLUSIVE,
            "core_dataset_end_exclusive": CORE_DATASET_END_EXCLUSIVE,
        },
        "bootstrap": {
            "seed_material": SEED_MATERIAL,
            "seed_material_sha256": SEED_MATERIAL_SHA256,
            "MARKET_02_BOOTSTRAP_SEED": MARKET_02_BOOTSTRAP_SEED,
            "json_twin_stored_numeric": JSON_TWIN_STORED_NUMERIC,
            "B": 999,
            "alpha": 0.05,
        },
        "result_artifact_path": RESULT_JSON_REL,
        "MARKET_02_TEST_CALIBRATED": False,
        "v3_reused_as_market_02_test": False,
        "default_v4": False,
        "b2_06_execution_authorized": False,
        "protected_oos_authorized": False,
        "funding_in_scope": False,
    }


def derive_market_02_run_identity(*args: Any, **kwargs: Any) -> str:
    _reject_caller_kwargs(args, kwargs)
    return _sha256_bytes(canonical_json_bytes(_scientific_run_identity_payload()))


def authenticate_market_02_implementation_freeze(*args: Any, **kwargs: Any) -> dict[str, Any]:
    _reject_caller_kwargs(args, kwargs)
    try:
        payload = _load_json(IMPL_FREEZE_JSON_REL)
        digest = sha256_file(_path(IMPL_FREEZE_JSON_REL))
    except OSError as exc:
        raise Market02ExecutionNotAuthorized(
            "MARKET_02_IMPLEMENTATION_FREEZE_MISSING"
        ) from exc
    if digest != IMPL_FREEZE_JSON_SHA256:
        raise Market02AuthorityError(
            f"MARKET_02_BYTE_IDENTITY_MISMATCH:{IMPL_FREEZE_JSON_REL}"
        )
    if _path(IMPL_FREEZE_JSON_REL).stat().st_size != IMPL_FREEZE_JSON_SIZE:
        raise Market02AuthorityError("MARKET_02_FREEZE_JSON_SIZE_MISMATCH")
    if payload.get("research_id") != RESEARCH_ID:
        raise Market02AuthorityError("MARKET_02_IMPLEMENTATION_FREEZE_IDENTITY_MISMATCH")
    reviewed = payload.get("reviewed_implementation") or {}
    if reviewed.get("head") != REVIEWED_IMPLEMENTATION_HEAD:
        raise Market02AuthorityError("MARKET_02_REVIEWED_HEAD_MISMATCH")
    if reviewed.get("tree") != REVIEWED_IMPLEMENTATION_TREE:
        raise Market02AuthorityError("MARKET_02_REVIEWED_TREE_MISMATCH")
    lib = (payload.get("accepted_scientific_implementation") or [{}])[0]
    if lib.get("reviewed_sha256") != LIB_REVIEWED_SHA256:
        raise Market02AuthorityError("MARKET_02_REVIEWED_LIB_MISMATCH")
    data = payload.get("data_authority") or {}
    if data.get("price_snapshot_id") != PRICE_SNAPSHOT_ID:
        raise Market02AuthorityError("MARKET_02_PRICE_SNAPSHOT_MISMATCH")
    if data.get("oi_snapshot_id") != OI_SNAPSHOT_ID:
        raise Market02AuthorityError("MARKET_02_OI_SNAPSHOT_MISMATCH")
    if data.get("common_start_inclusive") != COMMON_START_INCLUSIVE:
        raise Market02AuthorityError("MARKET_02_TIME_BOUNDS_MISMATCH")
    if data.get("common_end_exclusive") != COMMON_END_EXCLUSIVE:
        raise Market02AuthorityError("MARKET_02_TIME_BOUNDS_MISMATCH")
    seed = payload.get("seed_authority") or {}
    if seed.get("md_authoritative_seed") != MARKET_02_BOOTSTRAP_SEED:
        raise Market02AuthorityError("MARKET_02_SEED_AUTHORITY_MISMATCH")
    if seed.get("json_twin_stored_numeric") != JSON_TWIN_STORED_NUMERIC:
        raise Market02AuthorityError("MARKET_02_JSON_SEED_DISCREPANCY_MUTATED")
    if seed.get("silent_prereg_repair") is not False:
        raise Market02AuthorityError("MARKET_02_SILENT_PREREG_REPAIR")
    limits = payload.get("limitations_preserved") or {}
    if limits.get("MARKET_02_TEST_CALIBRATED") is not False:
        raise Market02AuthorityError("MARKET_02_TEST_CALIBRATED_MUTATED")
    if payload.get("explicit_state", {}).get("market_02_test_calibrated") is not False:
        raise Market02AuthorityError("MARKET_02_TEST_CALIBRATED_MUTATED")
    return {"payload": payload, "sha256": digest}


def authenticate_market_02_arm(*args: Any, **kwargs: Any) -> dict[str, Any]:
    _reject_caller_kwargs(args, kwargs)
    authenticate_frozen_prereg_bytes()
    authenticate_market_02_implementation_freeze()
    authenticate_market_02_implementation_bytes()
    authenticate_bound_input_identities()
    try:
        payload = _load_json(ARM_JSON_REL)
        digest = sha256_file(_path(ARM_JSON_REL))
    except OSError as exc:
        raise Market02NotArmed("MARKET_02_NOT_ARMED") from exc
    for field in ARM_OUTCOME_FIELDS:
        if field in payload:
            raise Market02AuthorityError("MARKET_02_ARM_CONTAINS_OUTCOME_FIELD")
    if payload.get("freeze_artifact_sha256") != IMPL_FREEZE_JSON_SHA256:
        raise Market02ExecutionNotAuthorized("MARKET_02_ARM_IDENTITY_MISMATCH")
    if payload.get("run_identity") != FROZEN_MARKET_02_RUN_IDENTITY:
        raise Market02ExecutionNotAuthorized("MARKET_02_ARM_RUN_IDENTITY_MISMATCH")
    derived = derive_market_02_run_identity()
    if payload.get("run_identity") != derived:
        raise Market02ExecutionNotAuthorized("MARKET_02_ARM_RUN_IDENTITY_MISMATCH")
    if payload.get("reviewed_implementation_head") != REVIEWED_IMPLEMENTATION_HEAD:
        raise Market02ExecutionNotAuthorized("MARKET_02_ARM_IMPLEMENTATION_MISMATCH")
    if payload.get("reviewed_implementation_tree") != REVIEWED_IMPLEMENTATION_TREE:
        raise Market02ExecutionNotAuthorized("MARKET_02_ARM_IMPLEMENTATION_MISMATCH")
    if payload.get("frozen_implementation_head") != FROZEN_IMPLEMENTATION_HEAD:
        raise Market02ExecutionNotAuthorized("MARKET_02_ARM_IMPLEMENTATION_MISMATCH")
    if payload.get("frozen_implementation_tree") != FROZEN_IMPLEMENTATION_TREE:
        raise Market02ExecutionNotAuthorized("MARKET_02_ARM_IMPLEMENTATION_MISMATCH")
    if payload.get("lib_reviewed_sha256") != LIB_REVIEWED_SHA256:
        raise Market02ExecutionNotAuthorized("MARKET_02_ARM_IMPLEMENTATION_MISMATCH")
    if payload.get("lib_armed_lifecycle_sha256") != LIB_ARMED_LIFECYCLE_SHA256:
        raise Market02ExecutionNotAuthorized("MARKET_02_ARM_IMPLEMENTATION_MISMATCH")
    if payload.get("price_snapshot_id") != PRICE_SNAPSHOT_ID:
        raise Market02ExecutionNotAuthorized("MARKET_02_ARM_SNAPSHOT_MISMATCH")
    if payload.get("oi_snapshot_id") != OI_SNAPSHOT_ID:
        raise Market02ExecutionNotAuthorized("MARKET_02_ARM_SNAPSHOT_MISMATCH")
    if payload.get("price_identity_sha256") != CORE_SNAPSHOT_IDENTITY_SHA256:
        raise Market02ExecutionNotAuthorized("MARKET_02_ARM_SNAPSHOT_MISMATCH")
    if payload.get("oi_identity_sha256") != OI_SNAPSHOT_IDENTITY_SHA256:
        raise Market02ExecutionNotAuthorized("MARKET_02_ARM_SNAPSHOT_MISMATCH")
    if payload.get("common_start_inclusive") != COMMON_START_INCLUSIVE:
        raise Market02ExecutionNotAuthorized("MARKET_02_ARM_TIME_BOUNDS_MISMATCH")
    if payload.get("common_end_exclusive") != COMMON_END_EXCLUSIVE:
        raise Market02ExecutionNotAuthorized("MARKET_02_ARM_TIME_BOUNDS_MISMATCH")
    if str(payload.get("MARKET_02_BOOTSTRAP_SEED")) != MARKET_02_BOOTSTRAP_SEED:
        raise Market02ExecutionNotAuthorized("MARKET_02_ARM_SEED_MISMATCH")
    if payload.get("result_artifact_path") != RESULT_JSON_REL:
        raise Market02ExecutionNotAuthorized("MARKET_02_ARM_RESULT_AUTHORITY_MISMATCH")
    if payload.get("authorization_consumed") is True:
        raise Market02ExecutionNotAuthorized("MARKET_02_ARM_CONSUMED")
    if int(payload.get("authorized_run_count", 0)) != 1:
        raise Market02ExecutionNotAuthorized("MARKET_02_ARM_RUN_COUNT_MISMATCH")
    if payload.get("MARKET_02_TEST_CALIBRATED") is not False:
        raise Market02AuthorityError("MARKET_02_TEST_CALIBRATED_MUTATED")
    if payload.get("DEFAULT_V4") is not False:
        raise Market02AuthorityError("MARKET_02_DEFAULT_V4_MUTATED")
    if payload.get("B2_06_EXECUTION_AUTHORIZED") is not False:
        raise Market02AuthorityError("MARKET_02_B2_06_MUTATED")
    if payload.get("v3_reused_as_market_02_test") is not False:
        raise Market02AuthorityError("MARKET_02_V3_CONTAMINATION")
    if payload.get("PROTECTED_OOS_AUTHORIZED") is not False:
        raise Market02AuthorityError("MARKET_02_PROTECTED_OOS_AUTHORIZED")
    if payload.get("json_twin_stored_numeric") != JSON_TWIN_STORED_NUMERIC:
        raise Market02AuthorityError("MARKET_02_JSON_SEED_DISCREPANCY_MUTATED")
    if digest != ARM_JSON_SHA256:
        raise Market02AuthorityError(f"MARKET_02_BYTE_IDENTITY_MISMATCH:{ARM_JSON_REL}")
    if _path(RESULT_JSON_REL).exists():
        raise Market02ExecutionNotAuthorized("MARKET_02_RESULT_ALREADY_EXISTS")
    return {"payload": payload, "sha256": digest, "run_identity": derived}


def authenticate_market_02_reservation(*args: Any, **kwargs: Any) -> dict[str, Any]:
    _reject_caller_kwargs(args, kwargs)
    try:
        payload = _load_json(RESERVATION_JSON_REL)
        digest = sha256_file(_path(RESERVATION_JSON_REL))
    except OSError as exc:
        raise Market02ExecutionNotAuthorized("MARKET_02_RESERVATION_MISSING") from exc
    if payload.get("run_identity") != FROZEN_MARKET_02_RUN_IDENTITY:
        raise Market02ExecutionNotAuthorized(
            "MARKET_02_RESERVATION_RUN_IDENTITY_MISMATCH"
        )
    if payload.get("arm_artifact_sha256") != ARM_JSON_SHA256:
        raise Market02ExecutionNotAuthorized("MARKET_02_RESERVATION_ARM_MISMATCH")
    if payload.get("result_artifact_path") != RESULT_JSON_REL:
        raise Market02ExecutionNotAuthorized(
            "MARKET_02_RESERVATION_RESULT_AUTHORITY_MISMATCH"
        )
    if int(payload.get("CANONICAL_EXECUTIONS_AUTHORIZED", 0)) != 1:
        raise Market02ExecutionNotAuthorized(
            "MARKET_02_RESERVATION_AUTHORIZED_MISMATCH"
        )
    if int(payload.get("CANONICAL_EXECUTIONS_CONSUMED", 1)) != 0:
        raise Market02ExecutionNotAuthorized("MARKET_02_RESERVATION_CONSUMED")
    if payload.get("rerun_preauthorized") is True:
        raise Market02ExecutionNotAuthorized("MARKET_02_RERUN_PREAUTHORIZED")
    if payload.get("MARKET_02_EXECUTED") is not False:
        raise Market02ExecutionNotAuthorized("MARKET_02_ALREADY_EXECUTED")
    if payload.get("MARKET_02_OUTCOME_INSPECTED") is not False:
        raise Market02ExecutionNotAuthorized("MARKET_02_OUTCOME_INSPECTED")
    if payload.get("MARKET_02_TEST_CALIBRATED") is not False:
        raise Market02AuthorityError("MARKET_02_TEST_CALIBRATED_MUTATED")
    if digest != RESERVATION_JSON_SHA256:
        raise Market02AuthorityError(
            f"MARKET_02_BYTE_IDENTITY_MISMATCH:{RESERVATION_JSON_REL}"
        )
    return {"payload": payload, "sha256": digest}


def authenticate_market_02_canonical_execution(*args: Any, **kwargs: Any) -> dict[str, Any]:
    _reject_caller_kwargs(args, kwargs)
    arm = authenticate_market_02_arm()
    reservation = authenticate_market_02_reservation()
    authenticate_arch_selector()
    return {
        "run_identity": arm["run_identity"],
        "arm": arm["payload"],
        "reservation": reservation["payload"],
    }


def authorize_bound_market_02_views(
    price_snapshot_id: str | None,
    oi_snapshot_id: str | None,
    *args: Any,
    **kwargs: Any,
) -> dict[str, Any]:
    _reject_caller_kwargs(args, kwargs)
    if price_snapshot_id != PRICE_SNAPSHOT_ID or oi_snapshot_id != OI_SNAPSHOT_ID:
        raise Market02ExecutionNotAuthorized("MARKET_02_SNAPSHOT_IDENTITY_MISMATCH")
    try:
        return authenticate_market_02_canonical_execution()
    except Market02AuthorityError as exc:
        raise Market02ExecutionNotAuthorized(str(exc)) from exc


def inspect_market_02_authorization_state() -> dict[str, Any]:
    try:
        arm = authenticate_market_02_arm()
        reservation = authenticate_market_02_reservation()
        consumed = int(reservation["payload"]["CANONICAL_EXECUTIONS_CONSUMED"])
        authorized = int(reservation["payload"]["CANONICAL_EXECUTIONS_AUTHORIZED"])
        return {
            "MARKET_02_ARMED": True,
            "MARKET_02_EXECUTION_AUTHORIZED": consumed == 0 and authorized == 1,
            "CANONICAL_EXECUTIONS_AUTHORIZED": authorized,
            "CANONICAL_EXECUTIONS_CONSUMED": consumed,
            "run_identity": arm["run_identity"],
            "MARKET_02_EXECUTED": False,
            "MARKET_02_OUTCOME_INSPECTED": False,
            "MARKET_02_TEST_CALIBRATED": False,
        }
    except (
        Market02AuthorityError,
        Market02ExecutionNotAuthorized,
        OSError,
        json.JSONDecodeError,
    ):
        return {
            "MARKET_02_ARMED": False,
            "MARKET_02_EXECUTION_AUTHORIZED": False,
            "CANONICAL_EXECUTIONS_AUTHORIZED": 0,
            "CANONICAL_EXECUTIONS_CONSUMED": 0,
            "run_identity": None,
            "MARKET_02_EXECUTED": False,
            "MARKET_02_OUTCOME_INSPECTED": False,
            "MARKET_02_TEST_CALIBRATED": False,
        }
