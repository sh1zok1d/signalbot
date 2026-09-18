"""MARKET-03 frozen identity and fail-closed bound-execution guard.

Does not evaluate MARKET-03 outcomes. Does not load the bound spot or
funding scientific snapshots into strategy logic.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Mapping


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


PREREG_MD_REL = "docs/research/MARKET_03_PUBLIC_STRATEGY_PREREG.md"
PREREG_JSON_REL = "docs/research/MARKET_03_PUBLIC_STRATEGY_PREREG.json"
PREREG_FREEZE_MD_REL = "docs/research/MARKET_03_PUBLIC_STRATEGY_PREREG_FREEZE.md"
PREREG_FREEZE_JSON_REL = "docs/research/MARKET_03_PUBLIC_STRATEGY_PREREG_FREEZE.json"
LIB_REL = "scripts/research/market_03_public_strategy_lib.py"
AUTHORITY_REL = "scripts/research/market_03_public_strategy_authority.py"
EXECUTE_REL = "scripts/research/market_03_public_strategy_execute.py"
PINNED_SOURCE_REL = "docs/research_data/MARKET_03_BTC_STRATEGY_LAB_B68A5518/"

RESEARCH_ID = "MARKET-03_PUBLIC_STRATEGY_REPLICATION"
REPLICATION_LEVEL = "LEVEL_2_FAITHFUL_REIMPLEMENTATION"
SCIENTIFIC_IDENTITY = "EXTERNAL_HISTORICAL_CLAIM_REPRODUCTION"

FROZEN_PREREG_MD_SHA256 = (
    "044bb2a6bbd51c49c856b02eb7866b43171664a05d947dce995489389eeb0b57"
)
FROZEN_PREREG_JSON_SHA256 = (
    "3f35f9a1d0575eaff3a1993a4779642259c0891dbdda1d49f22b958eba714f89"
)

EXTERNAL_REPO = "https://github.com/wiktorj137/btc-strategy-lab"
EXTERNAL_COMMIT = "b68a5518b4a3eba2fde1733160d7d7de356023b5"
EXTERNAL_TREE = "f7717e681c911ea3ccce15492246053cf15883cb"
FREQTRADE_ENGINE_DOCS_PIN = "2026.7"

SPOT_DATASET_ID = "MARKET_03_BINANCE_SPOT_BTCUSDT_1H_V0"
SPOT_SNAPSHOT_ID = "2ce1f504709dc40c37a70dddcf73acb444e715820e9c855f6817c48f10d2b345"
SPOT_DATA_SHA256 = "e560bebb6ba9d070ee0fa58aaa5cf922caaa24d4b7e2b4eac8c7c0041c9495d4"

FUNDING_DATASET_ID = "MARKET_03_BINANCE_UM_BTCUSDT_FUNDINGRATE_REST_V0"
FUNDING_SNAPSHOT_ID = "d47b7b78b6e7dbb842c7d9eb122c81063e0b804e179a53dd87723f9a8a8adc68"
FUNDING_DATA_SHA256 = "e7885cd53407d70b4627d58b9abf2cdf5b26cdc7097a139eac2e454ad75944cb"
FUNDING_ROWS = 5819
FUNDING_FIRST_UTC = "2019-09-10T08:00:00Z"
FUNDING_LAST_UTC = "2024-12-31T16:00:00Z"

B2_06_DATASET_ID = "B2_06_BINANCE_UM_BTCUSDT_OI_FUNDING_V0"
B2_06_SNAPSHOT_ID = "5a9d036b23721d75b519b8478b81e333791227376d25cbeea5f0666c90730a33"

WARMUP_START_INCLUSIVE = "2019-08-07T20:00:00Z"
WARMUP_END_EXCLUSIVE = "2019-10-01T00:00:00Z"
EVALUATION_START_INCLUSIVE = "2019-10-01T00:00:00Z"
EVALUATION_END_EXCLUSIVE = "2025-01-01T00:00:00Z"
PROTECTED_OOS_START = "2025-01-01T00:00:00Z"

STRICT_HISTORICAL_PUBLICATION_LATENCY = "UNPROVEN"
REPRODUCTION_FUNDINGTIME_ASSUMPTION = "ACCEPTABLE"

MARKET_03_BOUND_EXECUTION_AUTHORIZED = False
MARKET_03_ARMED = False
CANONICAL_EXECUTIONS_AUTHORIZED = 0
CANONICAL_EXECUTIONS_CONSUMED = 0
PROTECTED_OOS_AUTHORIZED = False
B2_06_EXECUTION_AUTHORIZED = False
IMPLEMENTATION_FROZEN = False

ALLOWED_TEST_ORIGINS = frozenset(
    {
        "synthetic",
        "pinned_external_fixture",
        "handcrafted",
    }
)
BOUND_SNAPSHOT_IDS = frozenset({SPOT_SNAPSHOT_ID, FUNDING_SNAPSHOT_ID})
BOUND_DATASET_IDS = frozenset({SPOT_DATASET_ID, FUNDING_DATASET_ID})

SPOT_BOUND_PATHS = (
    "docs/research_data/MARKET_03_BINANCE_SPOT_BTCUSDT_1H_V0/",
    "artifacts/research_data/MARKET_03_BINANCE_SPOT_BTCUSDT_1H_V0/",
)
FUNDING_BOUND_PATHS = (
    "docs/research_data/MARKET_03_BINANCE_UM_BTCUSDT_FUNDINGRATE_REST_V0/",
    "artifacts/research_data/MARKET_03_BINANCE_SPOT_BTCUSDT_1H_V0/"
    "canonical/BTCUSDT_UM_fundingRate_rest_authorized.jsonl",
)


class Market03AuthorityError(RuntimeError):
    """Frozen-authority or identity failure."""


class Market03ExecutionNotAuthorized(RuntimeError):
    def __init__(self, message: str = "MARKET_03_EXECUTION_NOT_AUTHORIZED") -> None:
        super().__init__(message)


class Market03BoundDataRefused(Market03ExecutionNotAuthorized):
    def __init__(
        self, message: str = "MARKET_03_BOUND_REAL_DATA_REFUSED_IMPLEMENTATION_UNIT"
    ) -> None:
        super().__init__(message)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _path(rel: str) -> Path:
    return _repo_root() / rel


def authenticate_frozen_prereg_bytes() -> dict[str, str]:
    md = sha256_file(_path(PREREG_MD_REL))
    js = sha256_file(_path(PREREG_JSON_REL))
    if md != FROZEN_PREREG_MD_SHA256 or js != FROZEN_PREREG_JSON_SHA256:
        raise Market03AuthorityError("MARKET_03_PREREG_BYTE_IDENTITY_MISMATCH")
    return {"prereg_md_sha256": md, "prereg_json_sha256": js}


def snapshot_is_bound(snapshot_id: str | None) -> bool:
    if snapshot_id is None:
        return False
    return snapshot_id in BOUND_SNAPSHOT_IDS or snapshot_id == B2_06_SNAPSHOT_ID


def dataset_is_bound(dataset_id: str | None) -> bool:
    if dataset_id is None:
        return False
    return dataset_id in BOUND_DATASET_IDS or dataset_id == B2_06_DATASET_ID


def origin_is_allowed_for_tests(origin: str | None) -> bool:
    return origin in ALLOWED_TEST_ORIGINS


def refuse_bound_execution(reason: str = "MARKET_03_EXECUTION_NOT_AUTHORIZED") -> None:
    raise Market03ExecutionNotAuthorized(reason)


def refuse_b2_06_as_authority() -> None:
    raise Market03AuthorityError("MARKET_03_B2_06_IS_NOT_FUNDING_AUTHORITY")


def _looks_like_bound_path(value: str) -> bool:
    normalized = value.replace("\\", "/")
    for prefix in SPOT_BOUND_PATHS + FUNDING_BOUND_PATHS:
        if prefix.rstrip("/") in normalized:
            return True
    if "MARKET_03_BINANCE_SPOT_BTCUSDT_1H_V0" in normalized:
        return True
    if "MARKET_03_BINANCE_UM_BTCUSDT_FUNDINGRATE_REST_V0" in normalized:
        return True
    if "BTCUSDT_UM_fundingRate_rest_authorized" in normalized:
        return True
    return False


def refuse_bound_scientific_inputs(
    *,
    origin: str | None,
    spot_snapshot_id: str | None = None,
    funding_snapshot_id: str | None = None,
    dataset_id: str | None = None,
    source_path: str | None = None,
    n_spot_rows: int | None = None,
    n_funding_rows: int | None = None,
) -> None:
    """Fail-closed guard for this implementation unit.

    Scientific functions may run on synthetic/fixture/handcrafted inputs.
    Bound real MARKET-03 snapshots cannot enter strategy logic while
    MARKET_03_BOUND_EXECUTION_AUTHORIZED is False.
    """
    if MARKET_03_BOUND_EXECUTION_AUTHORIZED:
        raise Market03AuthorityError("MARKET_03_BOUND_EXECUTION_FLAG_MUST_REMAIN_FALSE")

    if dataset_id == B2_06_DATASET_ID or funding_snapshot_id == B2_06_SNAPSHOT_ID:
        refuse_b2_06_as_authority()
    if dataset_is_bound(dataset_id) or snapshot_is_bound(spot_snapshot_id) or snapshot_is_bound(
        funding_snapshot_id
    ):
        raise Market03BoundDataRefused("MARKET_03_BOUND_SNAPSHOT_REFUSED")
    if source_path is not None and _looks_like_bound_path(str(source_path)):
        raise Market03BoundDataRefused("MARKET_03_BOUND_PATH_REFUSED")
    if n_funding_rows == FUNDING_ROWS and origin not in ALLOWED_TEST_ORIGINS:
        raise Market03BoundDataRefused("MARKET_03_BOUND_FUNDING_ROWCOUNT_REFUSED")
    if not origin_is_allowed_for_tests(origin):
        raise Market03BoundDataRefused("MARKET_03_ORIGIN_NOT_AUTHORIZED_FOR_IMPLEMENTATION_UNIT")


def inspect_market_03_authorization_state() -> dict[str, Any]:
    return {
        "MARKET_03_ARMED": MARKET_03_ARMED,
        "MARKET_03_BOUND_EXECUTION_AUTHORIZED": MARKET_03_BOUND_EXECUTION_AUTHORIZED,
        "IMPLEMENTATION_FROZEN": IMPLEMENTATION_FROZEN,
        "CANONICAL_EXECUTIONS_AUTHORIZED": CANONICAL_EXECUTIONS_AUTHORIZED,
        "CANONICAL_EXECUTIONS_CONSUMED": CANONICAL_EXECUTIONS_CONSUMED,
        "PROTECTED_OOS_AUTHORIZED": PROTECTED_OOS_AUTHORIZED,
        "B2_06_EXECUTION_AUTHORIZED": B2_06_EXECUTION_AUTHORIZED,
        "STRICT_HISTORICAL_PUBLICATION_LATENCY": STRICT_HISTORICAL_PUBLICATION_LATENCY,
        "REPRODUCTION_FUNDINGTIME_ASSUMPTION": REPRODUCTION_FUNDINGTIME_ASSUMPTION,
        "replication_level": REPLICATION_LEVEL,
    }


def require_external_source_identity(
    commit: str | None = None, tree: str | None = None
) -> None:
    if commit is not None and commit != EXTERNAL_COMMIT:
        raise Market03AuthorityError("MARKET_03_EXTERNAL_COMMIT_MISMATCH")
    if tree is not None and tree != EXTERNAL_TREE:
        raise Market03AuthorityError("MARKET_03_EXTERNAL_TREE_MISMATCH")


def caller_kwargs_rejected(args: tuple[Any, ...], kwargs: Mapping[str, Any]) -> None:
    if args or kwargs:
        raise Market03ExecutionNotAuthorized(
            "caller arguments cannot redefine MARKET-03 bound execution authority"
        )
