"""MARKET-03 one-shot ARM authority. Lifecycle only.

Lives outside the frozen scientific bytes
(``market_03_public_strategy_{lib,authority,execute}.py``). Does not
evaluate MARKET-03 outcomes. Does not load bound spot or funding rows
into strategy logic. Caller kwargs cannot substitute scientific
authority.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


PREREG_MD_REL = "docs/research/MARKET_03_PUBLIC_STRATEGY_PREREG.md"
PREREG_JSON_REL = "docs/research/MARKET_03_PUBLIC_STRATEGY_PREREG.json"
IMPL_FREEZE_MD_REL = (
    "docs/research/MARKET_03_PUBLIC_STRATEGY_IMPLEMENTATION_FREEZE.md"
)
IMPL_FREEZE_JSON_REL = (
    "docs/research/MARKET_03_PUBLIC_STRATEGY_IMPLEMENTATION_FREEZE.json"
)
ARM_MD_REL = "docs/research/MARKET_03_PUBLIC_STRATEGY_ARM.md"
ARM_JSON_REL = "docs/research/MARKET_03_PUBLIC_STRATEGY_ARM.json"
RESERVATION_JSON_REL = "docs/research/MARKET_03_PUBLIC_STRATEGY_RESERVATION.json"
LIB_REL = "scripts/research/market_03_public_strategy_lib.py"
AUTHORITY_REL = "scripts/research/market_03_public_strategy_authority.py"
EXECUTE_REL = "scripts/research/market_03_public_strategy_execute.py"
SPOT_SNAPSHOT_DOC_REL = (
    "docs/research_data/MARKET_03_BINANCE_SPOT_BTCUSDT_1H_V0/SNAPSHOT_2ce1f504.json"
)
FUNDING_SNAPSHOT_DOC_REL = (
    "docs/research_data/MARKET_03_BINANCE_UM_BTCUSDT_FUNDINGRATE_REST_V0/"
    "SNAPSHOT_d47b7b78.json"
)

RESEARCH_ID = "MARKET-03_PUBLIC_STRATEGY_REPLICATION"
UNIT_ID = "MARKET_03_PUBLIC_STRATEGY_ARM"

FROZEN_PREREG_MD_SHA256 = (
    "044bb2a6bbd51c49c856b02eb7866b43171664a05d947dce995489389eeb0b57"
)
FROZEN_PREREG_JSON_SHA256 = (
    "3f35f9a1d0575eaff3a1993a4779642259c0891dbdda1d49f22b958eba714f89"
)
IMPL_FREEZE_MD_SHA256 = (
    "5007575f5fa9d6860465341e5bf3f2fa0239e18f3290c35a55da4960d56ebc2f"
)
IMPL_FREEZE_JSON_SHA256 = (
    "ff5d53108219aa679463ac8fae8aa334eaf52f0c15d080831f319b2079c05068"
)
LIB_SHA256 = "46ec2449e967172b61eec32f5ab6caf897ff9db04249395ac55a2368840289a5"
AUTHORITY_SHA256 = (
    "97f000c6afc2427db9fe3f90548f77c7e7ab4da0e43ba3283159101565a305e4"
)
EXECUTE_SHA256 = "90fd315d926b2b957391ed31c71bff6a33b0f22257960d0779e27e277cb40bcf"

FROZEN_IMPLEMENTATION_HEAD = "03411aaa1a2f938169f07f8f3576f17227a2b14b"
FROZEN_IMPLEMENTATION_TREE = "87a1da250a56343c44625e3f5187a6877035d1da"

EXTERNAL_REPO = "https://github.com/wiktorj137/btc-strategy-lab"
EXTERNAL_COMMIT = "b68a5518b4a3eba2fde1733160d7d7de356023b5"
EXTERNAL_TREE = "f7717e681c911ea3ccce15492246053cf15883cb"
REPLICATION_LEVEL = "LEVEL_2_FAITHFUL_REIMPLEMENTATION"

SPOT_DATASET_ID = "MARKET_03_BINANCE_SPOT_BTCUSDT_1H_V0"
SPOT_SNAPSHOT_ID = "2ce1f504709dc40c37a70dddcf73acb444e715820e9c855f6817c48f10d2b345"
SPOT_DATA_SHA256 = "e560bebb6ba9d070ee0fa58aaa5cf922caaa24d4b7e2b4eac8c7c0041c9495d4"

FUNDING_DATASET_ID = "MARKET_03_BINANCE_UM_BTCUSDT_FUNDINGRATE_REST_V0"
FUNDING_SNAPSHOT_ID = "d47b7b78b6e7dbb842c7d9eb122c81063e0b804e179a53dd87723f9a8a8adc68"
FUNDING_DATA_SHA256 = "e7885cd53407d70b4627d58b9abf2cdf5b26cdc7097a139eac2e454ad75944cb"

B2_06_DATASET_ID = "B2_06_BINANCE_UM_BTCUSDT_OI_FUNDING_V0"
B2_06_SNAPSHOT_ID = "5a9d036b23721d75b519b8478b81e333791227376d25cbeea5f0666c90730a33"

WARMUP_START_INCLUSIVE = "2019-08-07T20:00:00Z"
WARMUP_END_EXCLUSIVE = "2019-10-01T00:00:00Z"
EVALUATION_START_INCLUSIVE = "2019-10-01T00:00:00Z"
EVALUATION_END_EXCLUSIVE = "2025-01-01T00:00:00Z"
PROTECTED_OOS_START = "2025-01-01T00:00:00Z"

PRIMARY_CLASSIFICATION_RULE = (
    "REPRODUCED_DIRECTION iff finite(MDD_filtered) and finite(MDD_baseline) "
    "and (MDD_filtered > MDD_baseline)"
)
REPRODUCTION_FUNDINGTIME_ASSUMPTION = "ACCEPTABLE"
STRICT_HISTORICAL_PUBLICATION_LATENCY = "UNPROVEN"

CANONICAL_EXECUTIONS_AUTHORIZED = 1
CANONICAL_EXECUTIONS_CONSUMED = 0
PROTECTED_OOS_AUTHORIZED = False
B2_06_EXECUTION_AUTHORIZED = False

ARM_JSON_SHA256 = "7c801cdc713d2b2a58c35f4b28a1cd8b6d464b7e06dace1c374ed46ef6a3075c"
ARM_MD_SHA256 = "ab268bfd1b5669ba33f700b540a15a91aedfb3bfc503ae7e9cd62e89b9f5970e"
RESERVATION_JSON_SHA256 = (
    "ebc4338acb308d544967558ff1fdf8b7d22740616d139de82b1b7912db60ef9f"
)
FROZEN_MARKET_03_RUN_IDENTITY = (
    "f68b6de7d6c127f67908c48bf4be73cf986ea5d9daf9257bdae07f9ac626f397"
)

ARM_OUTCOME_FIELDS = (
    "mdd_baseline",
    "mdd_filtered",
    "primary_classification",
    "baseline_trades",
    "filtered_trades",
    "wallet",
    "RESULT",
    "final_classification",
    "trade_count",
    "total_return",
)


class Market03ArmAuthorityError(RuntimeError):
    """ARM-authority or identity failure."""


class Market03CanonicalExecutionNotAuthorized(RuntimeError):
    def __init__(self, message: str = "MARKET_03_EXECUTION_NOT_AUTHORIZED") -> None:
        super().__init__(message)


class Market03CanonicalExecutionReserved(RuntimeError):
    def __init__(
        self,
        message: str = "MARKET_03_CANONICAL_EXECUTION_RESERVED_FOR_EXECUTION_UNIT",
    ) -> None:
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
        raise Market03CanonicalExecutionNotAuthorized(
            "caller arguments cannot redefine MARKET-03 ARM authority"
        )


def _path(rel: str) -> Path:
    return _repo_root() / rel


def _load_json(rel: str) -> dict[str, Any]:
    return json.loads(_path(rel).read_text(encoding="utf-8"))


def _require_file_sha256(rel: str, expected: str) -> str:
    digest = sha256_file(_path(rel))
    if digest != expected:
        raise Market03ArmAuthorityError(f"MARKET_03_BYTE_IDENTITY_MISMATCH:{rel}")
    return digest


def scientific_run_identity_payload() -> dict[str, Any]:
    return {
        "schema": "market_03_public_strategy_scientific_run_identity",
        "schema_version": "1.0.0",
        "research_id": RESEARCH_ID,
        "purpose": "CANONICAL_MARKET_03_EXECUTION",
        "prereg_md_sha256": FROZEN_PREREG_MD_SHA256,
        "prereg_json_sha256": FROZEN_PREREG_JSON_SHA256,
        "implementation_freeze_md_sha256": IMPL_FREEZE_MD_SHA256,
        "implementation_freeze_json_sha256": IMPL_FREEZE_JSON_SHA256,
        "frozen_implementation_head": FROZEN_IMPLEMENTATION_HEAD,
        "frozen_implementation_tree": FROZEN_IMPLEMENTATION_TREE,
        "lib_sha256": LIB_SHA256,
        "authority_sha256": AUTHORITY_SHA256,
        "execute_sha256": EXECUTE_SHA256,
        "external_repo": EXTERNAL_REPO,
        "external_commit": EXTERNAL_COMMIT,
        "external_tree": EXTERNAL_TREE,
        "replication_level": REPLICATION_LEVEL,
        "spot_dataset_id": SPOT_DATASET_ID,
        "spot_snapshot_id": SPOT_SNAPSHOT_ID,
        "spot_data_sha256": SPOT_DATA_SHA256,
        "funding_dataset_id": FUNDING_DATASET_ID,
        "funding_snapshot_id": FUNDING_SNAPSHOT_ID,
        "funding_data_sha256": FUNDING_DATA_SHA256,
        "warmup_interval": {
            "start_inclusive": WARMUP_START_INCLUSIVE,
            "end_exclusive": WARMUP_END_EXCLUSIVE,
        },
        "evaluation_interval": {
            "start_inclusive": EVALUATION_START_INCLUSIVE,
            "end_exclusive": EVALUATION_END_EXCLUSIVE,
        },
        "primary_classification_rule": PRIMARY_CLASSIFICATION_RULE,
        "mdd_signed": True,
        "magnitude_fidelity": "DESCRIPTIVE_ONLY",
        "REPRODUCTION_FUNDINGTIME_ASSUMPTION": REPRODUCTION_FUNDINGTIME_ASSUMPTION,
        "STRICT_HISTORICAL_PUBLICATION_LATENCY": STRICT_HISTORICAL_PUBLICATION_LATENCY,
        "b2_06_is_not_authority": True,
        "protected_oos_authorized": False,
    }


def derive_market_03_run_identity(*args: Any, **kwargs: Any) -> str:
    _reject_caller_kwargs(args, kwargs)
    return _sha256_bytes(canonical_json_bytes(scientific_run_identity_payload()))


def authenticate_frozen_prereg_bytes(*args: Any, **kwargs: Any) -> dict[str, str]:
    _reject_caller_kwargs(args, kwargs)
    md = sha256_file(_path(PREREG_MD_REL))
    js = sha256_file(_path(PREREG_JSON_REL))
    if md != FROZEN_PREREG_MD_SHA256 or js != FROZEN_PREREG_JSON_SHA256:
        raise Market03ArmAuthorityError("MARKET_03_PREREG_BYTE_IDENTITY_MISMATCH")
    return {"prereg_md_sha256": md, "prereg_json_sha256": js}


def authenticate_frozen_scientific_bytes(*args: Any, **kwargs: Any) -> None:
    _reject_caller_kwargs(args, kwargs)
    _require_file_sha256(LIB_REL, LIB_SHA256)
    _require_file_sha256(AUTHORITY_REL, AUTHORITY_SHA256)
    _require_file_sha256(EXECUTE_REL, EXECUTE_SHA256)


def authenticate_market_03_implementation_freeze(
    *args: Any, **kwargs: Any
) -> dict[str, Any]:
    _reject_caller_kwargs(args, kwargs)
    try:
        payload = _load_json(IMPL_FREEZE_JSON_REL)
        digest = sha256_file(_path(IMPL_FREEZE_JSON_REL))
        md_digest = sha256_file(_path(IMPL_FREEZE_MD_REL))
    except OSError as exc:
        raise Market03CanonicalExecutionNotAuthorized(
            "MARKET_03_IMPLEMENTATION_FREEZE_MISSING"
        ) from exc
    if digest != IMPL_FREEZE_JSON_SHA256:
        raise Market03ArmAuthorityError(
            f"MARKET_03_BYTE_IDENTITY_MISMATCH:{IMPL_FREEZE_JSON_REL}"
        )
    if md_digest != IMPL_FREEZE_MD_SHA256:
        raise Market03ArmAuthorityError(
            f"MARKET_03_BYTE_IDENTITY_MISMATCH:{IMPL_FREEZE_MD_REL}"
        )
    if payload.get("research_id") != RESEARCH_ID:
        raise Market03ArmAuthorityError("MARKET_03_IMPLEMENTATION_FREEZE_IDENTITY_MISMATCH")
    reviewed = payload.get("reviewed_implementation") or {}
    if reviewed.get("head") != FROZEN_IMPLEMENTATION_HEAD:
        raise Market03ArmAuthorityError("MARKET_03_REVIEWED_HEAD_MISMATCH")
    if reviewed.get("tree") != FROZEN_IMPLEMENTATION_TREE:
        raise Market03ArmAuthorityError("MARKET_03_REVIEWED_TREE_MISMATCH")
    if payload.get("status") != "IMPLEMENTATION_FROZEN":
        raise Market03ArmAuthorityError("MARKET_03_IMPLEMENTATION_FREEZE_STATUS_MISMATCH")
    return {"payload": payload, "sha256": digest, "md_sha256": md_digest}


def _reject_b2_06(dataset_id: Any, snapshot_id: Any, data_sha256: Any = None) -> None:
    if dataset_id == B2_06_DATASET_ID or snapshot_id == B2_06_SNAPSHOT_ID:
        raise Market03ArmAuthorityError("MARKET_03_B2_06_IS_NOT_FUNDING_AUTHORITY")
    if data_sha256 == B2_06_SNAPSHOT_ID:
        raise Market03ArmAuthorityError("MARKET_03_B2_06_IS_NOT_FUNDING_AUTHORITY")


def reject_protected_oos_extension(
    evaluation_end_exclusive: str | None,
    *args: Any,
    **kwargs: Any,
) -> None:
    _reject_caller_kwargs(args, kwargs)
    if evaluation_end_exclusive != EVALUATION_END_EXCLUSIVE:
        raise Market03CanonicalExecutionNotAuthorized(
            "MARKET_03_PROTECTED_OOS_EXTENSION_REFUSED"
        )
    if PROTECTED_OOS_AUTHORIZED is not False:
        raise Market03CanonicalExecutionNotAuthorized(
            "MARKET_03_PROTECTED_OOS_AUTHORIZED"
        )


def authenticate_spot_funding_authorities(*args: Any, **kwargs: Any) -> dict[str, Any]:
    _reject_caller_kwargs(args, kwargs)
    try:
        spot = _load_json(SPOT_SNAPSHOT_DOC_REL)
        funding = _load_json(FUNDING_SNAPSHOT_DOC_REL)
    except OSError as exc:
        raise Market03CanonicalExecutionNotAuthorized(
            "MARKET_03_SNAPSHOT_DOC_MISSING"
        ) from exc
    if spot.get("snapshot_id") != SPOT_SNAPSHOT_ID:
        raise Market03ArmAuthorityError("MARKET_03_SPOT_SNAPSHOT_MISMATCH")
    identity = spot.get("identity_payload") or {}
    if identity.get("dataset_id") != SPOT_DATASET_ID:
        raise Market03ArmAuthorityError("MARKET_03_SPOT_DATASET_MISMATCH")
    if identity.get("canonical_klines_sha256") != SPOT_DATA_SHA256:
        raise Market03ArmAuthorityError("MARKET_03_SPOT_DATA_SHA256_MISMATCH")
    if funding.get("snapshot_id") != FUNDING_SNAPSHOT_ID:
        raise Market03ArmAuthorityError("MARKET_03_FUNDING_SNAPSHOT_MISMATCH")
    f_identity = funding.get("identity_payload") or {}
    if f_identity.get("dataset_id") != FUNDING_DATASET_ID:
        raise Market03ArmAuthorityError("MARKET_03_FUNDING_DATASET_MISMATCH")
    if f_identity.get("canonical_funding_sha256") != FUNDING_DATA_SHA256:
        raise Market03ArmAuthorityError("MARKET_03_FUNDING_DATA_SHA256_MISMATCH")
    _reject_b2_06(f_identity.get("dataset_id"), funding.get("snapshot_id"))
    _reject_b2_06(identity.get("dataset_id"), spot.get("snapshot_id"))
    return {
        "spot_snapshot_id": SPOT_SNAPSHOT_ID,
        "funding_snapshot_id": FUNDING_SNAPSHOT_ID,
        "spot_rows_loaded_into_strategy": False,
        "funding_rows_loaded_into_strategy": False,
    }


def authenticate_market_03_arm(*args: Any, **kwargs: Any) -> dict[str, Any]:
    _reject_caller_kwargs(args, kwargs)
    authenticate_frozen_prereg_bytes()
    authenticate_market_03_implementation_freeze()
    authenticate_frozen_scientific_bytes()
    try:
        payload = _load_json(ARM_JSON_REL)
        digest = sha256_file(_path(ARM_JSON_REL))
    except OSError as exc:
        raise Market03CanonicalExecutionNotAuthorized("MARKET_03_ARM_MISSING") from exc
    for field in ARM_OUTCOME_FIELDS:
        if field in payload:
            raise Market03ArmAuthorityError("MARKET_03_ARM_CONTAINS_OUTCOME_FIELD")
    derived = derive_market_03_run_identity()
    if payload.get("run_identity") != FROZEN_MARKET_03_RUN_IDENTITY:
        raise Market03CanonicalExecutionNotAuthorized(
            "MARKET_03_ARM_RUN_IDENTITY_MISMATCH"
        )
    if payload.get("run_identity") != derived:
        raise Market03CanonicalExecutionNotAuthorized(
            "MARKET_03_ARM_RUN_IDENTITY_MISMATCH"
        )
    if payload.get("freeze_artifact_sha256") != IMPL_FREEZE_JSON_SHA256:
        raise Market03CanonicalExecutionNotAuthorized("MARKET_03_ARM_IDENTITY_MISMATCH")
    if payload.get("implementation_freeze_md_sha256") != IMPL_FREEZE_MD_SHA256:
        raise Market03CanonicalExecutionNotAuthorized("MARKET_03_ARM_IDENTITY_MISMATCH")
    if payload.get("implementation_freeze_json_sha256") != IMPL_FREEZE_JSON_SHA256:
        raise Market03CanonicalExecutionNotAuthorized("MARKET_03_ARM_IDENTITY_MISMATCH")
    if payload.get("prereg_md_sha256") != FROZEN_PREREG_MD_SHA256:
        raise Market03CanonicalExecutionNotAuthorized("MARKET_03_ARM_PREREG_MISMATCH")
    if payload.get("prereg_json_sha256") != FROZEN_PREREG_JSON_SHA256:
        raise Market03CanonicalExecutionNotAuthorized("MARKET_03_ARM_PREREG_MISMATCH")
    if payload.get("frozen_implementation_head") != FROZEN_IMPLEMENTATION_HEAD:
        raise Market03CanonicalExecutionNotAuthorized(
            "MARKET_03_ARM_IMPLEMENTATION_MISMATCH"
        )
    if payload.get("frozen_implementation_tree") != FROZEN_IMPLEMENTATION_TREE:
        raise Market03CanonicalExecutionNotAuthorized(
            "MARKET_03_ARM_IMPLEMENTATION_MISMATCH"
        )
    if payload.get("lib_sha256") != LIB_SHA256:
        raise Market03CanonicalExecutionNotAuthorized(
            "MARKET_03_ARM_IMPLEMENTATION_MISMATCH"
        )
    if payload.get("authority_sha256") != AUTHORITY_SHA256:
        raise Market03CanonicalExecutionNotAuthorized(
            "MARKET_03_ARM_IMPLEMENTATION_MISMATCH"
        )
    if payload.get("execute_sha256") != EXECUTE_SHA256:
        raise Market03CanonicalExecutionNotAuthorized(
            "MARKET_03_ARM_IMPLEMENTATION_MISMATCH"
        )
    if payload.get("external_commit") != EXTERNAL_COMMIT:
        raise Market03CanonicalExecutionNotAuthorized(
            "MARKET_03_ARM_EXTERNAL_COMMIT_MISMATCH"
        )
    if payload.get("external_tree") != EXTERNAL_TREE:
        raise Market03CanonicalExecutionNotAuthorized(
            "MARKET_03_ARM_EXTERNAL_TREE_MISMATCH"
        )
    if payload.get("replication_level") != REPLICATION_LEVEL:
        raise Market03CanonicalExecutionNotAuthorized(
            "MARKET_03_ARM_REPLICATION_LEVEL_MISMATCH"
        )
    _reject_b2_06(payload.get("funding_dataset_id"), payload.get("funding_snapshot_id"))
    _reject_b2_06(payload.get("spot_dataset_id"), payload.get("spot_snapshot_id"))
    if payload.get("spot_snapshot_id") != SPOT_SNAPSHOT_ID:
        raise Market03CanonicalExecutionNotAuthorized("MARKET_03_ARM_SNAPSHOT_MISMATCH")
    if payload.get("spot_dataset_id") != SPOT_DATASET_ID:
        raise Market03CanonicalExecutionNotAuthorized("MARKET_03_ARM_SNAPSHOT_MISMATCH")
    if payload.get("spot_data_sha256") != SPOT_DATA_SHA256:
        raise Market03CanonicalExecutionNotAuthorized("MARKET_03_ARM_SNAPSHOT_MISMATCH")
    if payload.get("funding_snapshot_id") != FUNDING_SNAPSHOT_ID:
        raise Market03CanonicalExecutionNotAuthorized("MARKET_03_ARM_SNAPSHOT_MISMATCH")
    if payload.get("funding_dataset_id") != FUNDING_DATASET_ID:
        raise Market03CanonicalExecutionNotAuthorized("MARKET_03_ARM_SNAPSHOT_MISMATCH")
    if payload.get("funding_data_sha256") != FUNDING_DATA_SHA256:
        raise Market03CanonicalExecutionNotAuthorized("MARKET_03_ARM_SNAPSHOT_MISMATCH")
    if payload.get("primary_classification_rule") != PRIMARY_CLASSIFICATION_RULE:
        raise Market03CanonicalExecutionNotAuthorized(
            "MARKET_03_ARM_PRIMARY_RULE_MISMATCH"
        )
    if payload.get("REPRODUCTION_FUNDINGTIME_ASSUMPTION") != (
        REPRODUCTION_FUNDINGTIME_ASSUMPTION
    ):
        raise Market03CanonicalExecutionNotAuthorized(
            "MARKET_03_ARM_FUNDINGTIME_ASSUMPTION_MISMATCH"
        )
    if payload.get("STRICT_HISTORICAL_PUBLICATION_LATENCY") != (
        STRICT_HISTORICAL_PUBLICATION_LATENCY
    ):
        raise Market03CanonicalExecutionNotAuthorized(
            "MARKET_03_ARM_PUBLICATION_LATENCY_MISMATCH"
        )
    reject_protected_oos_extension(payload.get("evaluation_end_exclusive"))
    if payload.get("warmup_start_inclusive") != WARMUP_START_INCLUSIVE:
        raise Market03CanonicalExecutionNotAuthorized(
            "MARKET_03_ARM_WARMUP_INTERVAL_MISMATCH"
        )
    if payload.get("evaluation_start_inclusive") != EVALUATION_START_INCLUSIVE:
        raise Market03CanonicalExecutionNotAuthorized(
            "MARKET_03_ARM_EVALUATION_INTERVAL_MISMATCH"
        )
    if payload.get("authorization_consumed") is True:
        raise Market03CanonicalExecutionNotAuthorized("MARKET_03_ARM_CONSUMED")
    if int(payload.get("authorized_run_count", 0)) != 1:
        raise Market03CanonicalExecutionNotAuthorized(
            "MARKET_03_ARM_AUTHORIZED_MISMATCH"
        )
    if int(payload.get("CANONICAL_EXECUTIONS_AUTHORIZED", 0)) != 1:
        raise Market03CanonicalExecutionNotAuthorized(
            "MARKET_03_ARM_AUTHORIZED_MISMATCH"
        )
    if int(payload.get("CANONICAL_EXECUTIONS_CONSUMED", 1)) != 0:
        raise Market03CanonicalExecutionNotAuthorized("MARKET_03_ARM_CONSUMED")
    if payload.get("MARKET_03_ARMED") is not True:
        raise Market03CanonicalExecutionNotAuthorized("MARKET_03_ARM_FLAG_MISMATCH")
    if payload.get("MARKET_03_STRATEGY_EXECUTED") is not False:
        raise Market03CanonicalExecutionNotAuthorized("MARKET_03_ALREADY_EXECUTED")
    if payload.get("MARKET_03_OUTCOMES_INSPECTED") is not False:
        raise Market03CanonicalExecutionNotAuthorized("MARKET_03_OUTCOME_INSPECTED")
    if payload.get("B2_06_EXECUTION_AUTHORIZED") is not False:
        raise Market03ArmAuthorityError("MARKET_03_B2_06_MUTATED")
    if payload.get("PROTECTED_OOS_AUTHORIZED") is not False:
        raise Market03ArmAuthorityError("MARKET_03_PROTECTED_OOS_MUTATED")
    if digest != ARM_JSON_SHA256:
        raise Market03ArmAuthorityError("MARKET_03_ARM_HASH_MISMATCH")
    try:
        md_digest = sha256_file(_path(ARM_MD_REL))
    except OSError as exc:
        raise Market03CanonicalExecutionNotAuthorized("MARKET_03_ARM_MD_MISSING") from exc
    if md_digest != ARM_MD_SHA256:
        raise Market03ArmAuthorityError("MARKET_03_ARM_MD_HASH_MISMATCH")
    return {"payload": payload, "sha256": digest, "run_identity": derived}


def authenticate_market_03_reservation(*args: Any, **kwargs: Any) -> dict[str, Any]:
    _reject_caller_kwargs(args, kwargs)
    try:
        payload = _load_json(RESERVATION_JSON_REL)
        digest = sha256_file(_path(RESERVATION_JSON_REL))
    except OSError as exc:
        raise Market03CanonicalExecutionNotAuthorized(
            "MARKET_03_RESERVATION_MISSING"
        ) from exc
    if payload.get("run_identity") != FROZEN_MARKET_03_RUN_IDENTITY:
        raise Market03CanonicalExecutionNotAuthorized(
            "MARKET_03_RESERVATION_RUN_IDENTITY_MISMATCH"
        )
    if payload.get("arm_artifact_sha256") != ARM_JSON_SHA256:
        raise Market03CanonicalExecutionNotAuthorized(
            "MARKET_03_RESERVATION_ARM_MISMATCH"
        )
    if int(payload.get("CANONICAL_EXECUTIONS_AUTHORIZED", 0)) != 1:
        raise Market03CanonicalExecutionNotAuthorized(
            "MARKET_03_RESERVATION_AUTHORIZED_MISMATCH"
        )
    if int(payload.get("CANONICAL_EXECUTIONS_CONSUMED", 1)) != 0:
        raise Market03CanonicalExecutionNotAuthorized("MARKET_03_RESERVATION_CONSUMED")
    if payload.get("rerun_preauthorized") is True:
        raise Market03CanonicalExecutionNotAuthorized("MARKET_03_RERUN_PREAUTHORIZED")
    if payload.get("MARKET_03_STRATEGY_EXECUTED") is not False:
        raise Market03CanonicalExecutionNotAuthorized("MARKET_03_ALREADY_EXECUTED")
    if payload.get("MARKET_03_OUTCOMES_INSPECTED") is not False:
        raise Market03CanonicalExecutionNotAuthorized("MARKET_03_OUTCOME_INSPECTED")
    if payload.get("B2_06_EXECUTION_AUTHORIZED") is not False:
        raise Market03ArmAuthorityError("MARKET_03_B2_06_MUTATED")
    if digest != RESERVATION_JSON_SHA256:
        raise Market03ArmAuthorityError(
            f"MARKET_03_BYTE_IDENTITY_MISMATCH:{RESERVATION_JSON_REL}"
        )
    return {"payload": payload, "sha256": digest}


def authenticate_market_03_canonical_execution(
    *args: Any, **kwargs: Any
) -> dict[str, Any]:
    _reject_caller_kwargs(args, kwargs)
    arm = authenticate_market_03_arm()
    reservation = authenticate_market_03_reservation()
    authenticate_spot_funding_authorities()
    reject_protected_oos_extension(EVALUATION_END_EXCLUSIVE)
    return {
        "run_identity": arm["run_identity"],
        "arm": arm["payload"],
        "reservation": reservation["payload"],
        "arm_sha256": arm["sha256"],
        "reservation_sha256": reservation["sha256"],
    }


def inspect_market_03_arm_state() -> dict[str, Any]:
    """ARM-lifecycle inspect. Distinct from frozen inspect_market_03_authorization_state."""
    try:
        arm = authenticate_market_03_arm()
        reservation = authenticate_market_03_reservation()
        consumed = int(reservation["payload"]["CANONICAL_EXECUTIONS_CONSUMED"])
        authorized = int(reservation["payload"]["CANONICAL_EXECUTIONS_AUTHORIZED"])
        return {
            "MARKET_03_ARMED": True,
            "IMPLEMENTATION_FROZEN": True,
            "MARKET_03_EXECUTION_AUTHORIZED": consumed == 0 and authorized == 1,
            "CANONICAL_EXECUTIONS_AUTHORIZED": authorized,
            "CANONICAL_EXECUTIONS_CONSUMED": consumed,
            "run_identity": arm["run_identity"],
            "MARKET_03_STRATEGY_EXECUTED": False,
            "MARKET_03_OUTCOMES_INSPECTED": False,
            "MARKET_03_PARAMETER_SEARCH": False,
            "PROTECTED_OOS_TOUCHED": False,
            "B2_06_EXECUTION_AUTHORIZED": False,
        }
    except (
        Market03ArmAuthorityError,
        Market03CanonicalExecutionNotAuthorized,
        OSError,
        json.JSONDecodeError,
    ):
        return {
            "MARKET_03_ARMED": False,
            "IMPLEMENTATION_FROZEN": False,
            "MARKET_03_EXECUTION_AUTHORIZED": False,
            "CANONICAL_EXECUTIONS_AUTHORIZED": 0,
            "CANONICAL_EXECUTIONS_CONSUMED": 0,
            "run_identity": None,
            "MARKET_03_STRATEGY_EXECUTED": False,
            "MARKET_03_OUTCOMES_INSPECTED": False,
            "MARKET_03_PARAMETER_SEARCH": False,
            "PROTECTED_OOS_TOUCHED": False,
            "B2_06_EXECUTION_AUTHORIZED": False,
        }


def consume_authorization_atomically(*args: Any, **kwargs: Any) -> dict[str, str]:
    """Single-use 1/0 → 1/1. Future execution unit only. Not invoked by ARM main."""
    _reject_caller_kwargs(args, kwargs)
    authenticate_market_03_canonical_execution()
    reservation_path = _path(RESERVATION_JSON_REL)
    arm_path = _path(ARM_JSON_REL)
    reservation = json.loads(reservation_path.read_text(encoding="utf-8"))
    arm = json.loads(arm_path.read_text(encoding="utf-8"))
    if int(reservation.get("CANONICAL_EXECUTIONS_AUTHORIZED", 0)) != 1:
        raise Market03CanonicalExecutionNotAuthorized(
            "MARKET_03_RESERVATION_AUTHORIZED_MISMATCH"
        )
    if int(reservation.get("CANONICAL_EXECUTIONS_CONSUMED", 1)) != 0:
        raise Market03CanonicalExecutionNotAuthorized("MARKET_03_RESERVATION_CONSUMED")
    if arm.get("authorization_consumed") is True:
        raise Market03CanonicalExecutionNotAuthorized("MARKET_03_ARM_CONSUMED")
    reservation["CANONICAL_EXECUTIONS_CONSUMED"] = 1
    reservation["MARKET_03_STRATEGY_EXECUTED"] = True
    reservation["status"] = "CONSUMED"
    reservation["lifecycle"] = "CONSUMED"
    reservation["rerun_preauthorized"] = False
    reservation["replacement_reservation_preauthorized"] = False
    arm["authorization_consumed"] = True
    arm["CANONICAL_EXECUTIONS_CONSUMED"] = 1
    arm["MARKET_03_STRATEGY_EXECUTED"] = True
    arm["status"] = "EXECUTED"
    arm["lifecycle"] = "CONSUMED_EXECUTED"
    reservation_path.write_bytes(canonical_json_bytes(reservation))
    arm_path.write_bytes(canonical_json_bytes(arm))
    return {
        "reservation_sha256_consumed": sha256_file(reservation_path),
        "arm_sha256_consumed": sha256_file(arm_path),
        "CANONICAL_EXECUTIONS_AUTHORIZED": "1",
        "CANONICAL_EXECUTIONS_CONSUMED": "1",
    }
