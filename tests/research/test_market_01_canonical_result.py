"""Post-seal MARKET-01 RESULT identity checks. Does not rerun science."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from scripts.research.market_01_oi_expansion_weak_continuation_authority import (
    ARM_JSON_SHA256,
    FROZEN_MARKET_01_RUN_IDENTITY,
    FROZEN_PREREG_JSON_SHA256,
    FROZEN_PREREG_MD_SHA256,
    Market01ExecutionNotAuthorized,
    OI_SNAPSHOT_ID,
    PRICE_SNAPSHOT_ID,
    RESERVATION_JSON_SHA256,
    authenticate_market_01_canonical_execution,
)
from scripts.research.market_01_oi_expansion_weak_continuation_lib import dumps_result


REPO = Path(__file__).resolve().parents[2]
RESULT = REPO / "docs" / "research" / "MARKET_01_OI_EXPANSION_WEAK_CONTINUATION_RESULT.json"
SIDECAR = REPO / "docs" / "research" / "MARKET_01_OI_EXPANSION_WEAK_CONTINUATION_RESULT.json.sha256"
EXPECTED_SHA256 = "5310946b44dd3ebc609d05a13f92f6cb414e3a0727141d0ee324bce0aa626c5e"


def test_sealed_result_sha256_and_replay_without_rerun():
    raw = RESULT.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    assert digest == EXPECTED_SHA256
    assert SIDECAR.read_text(encoding="utf-8").strip() == EXPECTED_SHA256
    payload = json.loads(raw)
    replay = dumps_result(payload)
    if not replay.endswith("\n"):
        replay += "\n"
    assert hashlib.sha256(replay.encode("utf-8")).hexdigest() == EXPECTED_SHA256


def test_sealed_result_bindings_and_classification():
    payload = json.loads(RESULT.read_text(encoding="utf-8"))
    assert payload["canonical_run_identity"] == FROZEN_MARKET_01_RUN_IDENTITY
    assert payload["arm_artifact_sha256_unused"] == ARM_JSON_SHA256
    assert payload["reservation_sha256_unused"] == RESERVATION_JSON_SHA256
    assert payload["prereg_md_sha256"] == FROZEN_PREREG_MD_SHA256
    assert payload["prereg_json_sha256"] == FROZEN_PREREG_JSON_SHA256
    assert payload["price_snapshot_id"] == PRICE_SNAPSHOT_ID
    assert payload["oi_snapshot_id"] == OI_SNAPSHOT_ID
    assert payload["CANONICAL_EXECUTIONS_AUTHORIZED"] == 1
    assert payload["CANONICAL_EXECUTIONS_CONSUMED"] == 1
    assert payload["final_classification"] == "NO_EVIDENCE"
    assert payload["detected"] is False
    assert payload["MARKET_01_TEST_CALIBRATED"] is False
    assert payload["PROTECTED_OOS_TOUCHED"] is False
    assert payload["B2_06_EXECUTION_AUTHORIZED"] is False
    assert payload["DEFAULT_V4"] is False
    assert payload["rerun_occurred"] is False
    assert payload["funding_in_scope"] is False
    assert payload["robustness"] is None


def test_canonical_execution_refuses_second_run():
    with pytest.raises(Market01ExecutionNotAuthorized):
        authenticate_market_01_canonical_execution()
