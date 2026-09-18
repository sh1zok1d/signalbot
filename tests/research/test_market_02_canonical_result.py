"""Post-seal MARKET-02 RESULT identity checks. Does not rerun science."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from scripts.research.market_02_oi_expansion_price_confirmation_authority import (
    ARM_JSON_SHA256,
    FROZEN_IMPLEMENTATION_HEAD,
    FROZEN_IMPLEMENTATION_TREE,
    FROZEN_MARKET_02_RUN_IDENTITY,
    FROZEN_PREREG_JSON_SHA256,
    FROZEN_PREREG_MD_SHA256,
    IMPL_FREEZE_JSON_SHA256,
    LIB_ARMED_LIFECYCLE_SHA256,
    LIB_REVIEWED_SHA256,
    Market02ExecutionNotAuthorized,
    OI_SNAPSHOT_ID,
    PRICE_SNAPSHOT_ID,
    RESERVATION_JSON_SHA256,
    authenticate_market_02_canonical_execution,
)
from scripts.research.market_02_oi_expansion_price_confirmation_lib import dumps_result


REPO = Path(__file__).resolve().parents[2]
RESULT = REPO / "docs" / "research" / "MARKET_02_OI_EXPANSION_PRICE_CONFIRMATION_RESULT.json"
SIDECAR = REPO / "docs" / "research" / "MARKET_02_OI_EXPANSION_PRICE_CONFIRMATION_RESULT.json.sha256"
EXPECTED_SHA256 = "68e084b35201d227ecd9f48e99cc65a937b15fcb55a5849b1630c5d61850b478"
ARMED_HEAD = "6486dfadd920fc24a72fabe37d7dd906154cbc76"
ARMED_TREE = "6f022334ea015756c8551bad73debed81ba4f8a9"


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
    assert payload["canonical_run_identity"] == FROZEN_MARKET_02_RUN_IDENTITY
    assert payload["arm_artifact_sha256_unused"] == ARM_JSON_SHA256
    assert payload["reservation_sha256_unused"] == RESERVATION_JSON_SHA256
    assert payload["prereg_md_sha256"] == FROZEN_PREREG_MD_SHA256
    assert payload["prereg_json_sha256"] == FROZEN_PREREG_JSON_SHA256
    assert payload["implementation_freeze_json_sha256"] == IMPL_FREEZE_JSON_SHA256
    assert payload["lib_reviewed_sha256"] == LIB_REVIEWED_SHA256
    assert payload["lib_armed_lifecycle_sha256"] == LIB_ARMED_LIFECYCLE_SHA256
    assert payload["price_snapshot_id"] == PRICE_SNAPSHOT_ID
    assert payload["price_identity_sha256"] == "a104a4036ed7b4c7a4a9954ce1aeee247b6bbbb91d6abf2563b78b6bd9f84630"
    assert payload["oi_snapshot_id"] == OI_SNAPSHOT_ID
    assert payload["oi_identity_sha256"] == "bb216f9abdb9fcd7c7648bbffb8541e811af06498d062faa5f31037793768e5e"
    assert payload["execution_head"] == ARMED_HEAD
    assert payload["execution_tree"] == ARMED_TREE
    assert payload["frozen_implementation_head"] == FROZEN_IMPLEMENTATION_HEAD
    assert payload["frozen_implementation_tree"] == FROZEN_IMPLEMENTATION_TREE
    assert payload["CANONICAL_EXECUTIONS_AUTHORIZED"] == 1
    assert payload["CANONICAL_EXECUTIONS_CONSUMED"] == 1
    assert payload["final_classification"] == "NO_EVIDENCE"
    assert payload["detected"] is False
    assert payload["MARKET_02_TEST_CALIBRATED"] is False
    assert payload["PROTECTED_OOS_TOUCHED"] is False
    assert payload["B2_06_EXECUTION_AUTHORIZED"] is False
    assert payload["DEFAULT_V4"] is False
    assert payload["rerun_occurred"] is False
    assert payload["funding_in_scope"] is False
    assert payload["robustness"] is None
    assert payload["MARKET_02_BOOTSTRAP_SEED"] == "1852983754304692007"
    assert payload["price_load"]["forbidden_2025_2026_opened"] is False
    assert payload["oi_load"]["funding_jsonl_opened"] is False


def test_canonical_execution_refuses_second_run():
    with pytest.raises(Market02ExecutionNotAuthorized):
        authenticate_market_02_canonical_execution()
