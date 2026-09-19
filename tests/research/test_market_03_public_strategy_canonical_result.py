"""MARKET-03 canonical RESULT identity checks.

Does not rerun the scientific path or load bound series into strategy
logic. Locks the sealed RESULT and consumed reservation.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from scripts.research.market_03_public_strategy_arm_authority import (
    ARM_JSON_SHA256,
    ARM_MD_SHA256,
    FROZEN_MARKET_03_RUN_IDENTITY,
    Market03CanonicalExecutionNotAuthorized,
    RESERVATION_JSON_SHA256,
    authenticate_market_03_canonical_execution,
    consume_authorization_atomically,
    derive_market_03_run_identity,
)
from scripts.research.market_03_public_strategy_canonical_execution import (
    execute_authorized_canonical_market_03,
    run_canonical_market_03,
)


REPO = Path(__file__).resolve().parents[2]
RESULT_JSON = REPO / "docs/research/MARKET_03_PUBLIC_STRATEGY_RESULT.json"
RESULT_MD = REPO / "docs/research/MARKET_03_PUBLIC_STRATEGY_RESULT.md"
RESULT_JSON_SHA256 = "32b9157f9e4ce285627030218c0b9e37bed1347e6d4a30e2bd8e8ca87d46976e"
RESULT_MD_SHA256 = "a338f09d0cf0cc87879c6547b8058740bcf085c6f1e59bab9148f6825eae79bc"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_result_bytes_and_primary_classification_are_sealed():
    assert _sha256(RESULT_JSON) == RESULT_JSON_SHA256
    assert _sha256(RESULT_MD) == RESULT_MD_SHA256
    payload = json.loads(RESULT_JSON.read_text(encoding="utf-8"))
    assert payload["canonical_run_identity"] == FROZEN_MARKET_03_RUN_IDENTITY
    assert derive_market_03_run_identity() == FROZEN_MARKET_03_RUN_IDENTITY
    assert payload["primary_classification"] == "REPRODUCED_DIRECTION"
    assert payload["CANONICAL_EXECUTIONS_AUTHORIZED"] == 1
    assert payload["CANONICAL_EXECUTIONS_CONSUMED"] == 1
    assert payload["mdd_filtered"] > payload["mdd_baseline"]
    assert payload["PROTECTED_OOS_TOUCHED"] is False
    assert payload["MARKET_03_PARAMETER_SEARCH"] is False
    assert payload["arm_json_sha256_unused"] == ARM_JSON_SHA256
    assert payload["arm_md_sha256_unused"] == ARM_MD_SHA256
    assert payload["reservation_sha256_unused"] == RESERVATION_JSON_SHA256
    assert payload["max_scientifically_consumed_market_timestamp"] == (
        "2024-12-31T23:00:00Z"
    )


def test_second_canonical_execution_refuses_without_science():
    with pytest.raises(Market03CanonicalExecutionNotAuthorized, match="CONSUMED"):
        authenticate_market_03_canonical_execution()
    with pytest.raises(Market03CanonicalExecutionNotAuthorized, match="CONSUMED"):
        consume_authorization_atomically()
    assert run_canonical_market_03() == 3
    assert execute_authorized_canonical_market_03() == 3
    assert _sha256(RESULT_JSON) == RESULT_JSON_SHA256
