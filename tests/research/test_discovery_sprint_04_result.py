"""Persisted Sprint 04 RESULT identity tests. Do not re-execute science."""

from __future__ import annotations

import json
from pathlib import Path

from scripts.research.discovery_sprint_04 import common as C
from scripts.research.discovery_sprint_04 import execute_scientific as EX

REPO = Path(__file__).resolve().parents[2]
D12_PATH = REPO / "docs/research/discovery_results/D12_DISCOVERY_RESULT.json"
D13_PATH = REPO / "docs/research/discovery_results/D13_DISCOVERY_RESULT.json"
BATCH_PATH = REPO / "docs/research/DISCOVERY_SPRINT_04_RESULT.json"
FREEZE_PATH = REPO / "docs/research/DISCOVERY_SPRINT_04_IMPLEMENTATION_FREEZE.json"
PERMIT_PATH = REPO / "docs/research/DISCOVERY_SPRINT_04_EXECUTION_PERMIT.json"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_common_execution_authorized_remains_false_after_result():
    assert C.EXECUTION_AUTHORIZED is False


def test_d12_persisted_result_identity():
    payload = _load(D12_PATH)
    freeze = _load(FREEZE_PATH)
    permit = _load(PERMIT_PATH)
    assert payload["CLASSIFICATION"] == "PROMISING_PROTOTYPE"
    assert payload["IDENTITY_OK"] is True
    assert payload["SUPPORT_PASS"] is True
    assert payload["US_TRANSITION_N"] == 10
    assert payload["PSEUDO_SUNDAY_N"] == 239
    assert payload["STATISTICAL_GATE"] is True
    assert payload["PRACTICAL_GATE"] is True
    assert payload["TEMPORAL_GATE"] is True
    assert payload["EU_DIAGNOSTIC_AFFECTS_CLASSIFICATION"] is False
    assert payload["RANDOM_SEED"] == 20260922196
    assert payload["EXECUTION_ROOT"] == EX.EXECUTION_ROOT
    assert payload["IMPLEMENTATION_HASHES"] == freeze["IMPLEMENTATION_HASHES"]
    assert payload["PERMIT_SHA256"] == permit["PERMIT_SHA256"]
    assert payload["PROTECTED_2025_OPENED"] is False
    assert payload["PROTECTED_2026_OPENED"] is False
    assert payload["MARKET_07_CREATED"] is False
    assert payload["D7_RERUN_PERFORMED"] is False
    assert payload["D8_EXECUTED"] is False
    assert payload["RESULT_PAYLOAD_SHA256"] == EX.payload_sha256(payload)
    assert payload["RESULT_PAYLOAD_SHA256"] == (
        "73299c8d8313c7c73f423bb83565a45e3c17da6a534dbc8dc8fbf12f943b6feb"
    )
    assert payload["MEAN_A"] == 0.1335535649302866
    assert payload["MC_P"] == 9.999000099990002e-05
    yearly = payload["YEARLY_MEAN_A"]
    assert yearly["2022"] < 0
    assert sum(1 for v in yearly.values() if v > 0) == 4
    assert payload["EU_DIAGNOSTIC"]["MEAN_A"] == -0.17392447104949169


def test_d13_persisted_result_identity():
    payload = _load(D13_PATH)
    freeze = _load(FREEZE_PATH)
    assert payload["CLASSIFICATION"] == "NO_USEFUL_STRUCTURE"
    assert payload["IDENTITY_OK"] is True
    assert payload["SUPPORT_PASS"] is True
    assert payload["N"] == 82
    assert payload["WEEK_N"] == 256
    assert payload["NO_POST_T_CLOSE_SELECTED_N"] == 0
    assert payload["POOLED_IC_SIGN"] == -1
    assert payload["STRUCTURE_LABEL"] == "REVERSAL"
    assert payload["STATISTICAL_GATE"] is True
    assert payload["PRACTICAL_GATE"] is False
    assert payload["TEMPORAL_GATE"] is True
    assert payload["FRICTION_FLOOR"] == 0.004
    assert payload["RANDOM_SEED"] == 20260922197
    assert payload["DATA_IDENTITY"]["SNAPSHOT_ID"] == freeze["D13_SNAPSHOT_ID"]
    assert payload["DATA_IDENTITY"]["FILE_LEDGER_DIGEST"] == freeze["D13_FILE_LEDGER_DIGEST"]
    assert payload["DATA_IDENTITY"]["UNIVERSE_IDENTITY_DIGEST"] == freeze["D13_UNIVERSE_IDENTITY_DIGEST"]
    assert payload["RUNTIME_FILE_AUTHORITY"] == "SNAPSHOT_BOUND_OBJECT_LEDGER"
    assert payload["MEAN_WEEKLY_IC"] == -0.027440631083253317
    assert payload["MC_P"] == 0.015598440155984402
    assert payload["SIGNED_TOP_BOTTOM_SPREAD"] == -0.007875047071699056
    assert payload["SIGNED_TOP_BOTTOM_SPREAD"] < payload["FRICTION_FLOOR"]
    assert payload["RESULT_PAYLOAD_SHA256"] == EX.payload_sha256(payload)
    assert payload["RESULT_PAYLOAD_SHA256"] == (
        "c18f7de5821d8ee808732e0278afa53f622bb977d77f1ec71ee7423c96f5effd"
    )
    yearly = payload["YEARLY_MEAN_IC"]
    pooled_sign = payload["POOLED_IC_SIGN"]
    same = sum(1 for v in yearly.values() if (v > 0) - (v < 0) == pooled_sign)
    assert same == 4
    assert payload["PROTECTED_2025_OPENED"] is False
    assert payload["PROTECTED_2026_OPENED"] is False
    assert payload["MARKET_07_CREATED"] is False
    assert payload["D7_RERUN_PERFORMED"] is False
    assert payload["D8_EXECUTED"] is False


def test_sprint04_batch_result_and_counters():
    batch = _load(BATCH_PATH)
    assert batch["D12_CLASSIFICATION"] == "PROMISING_PROTOTYPE"
    assert batch["D13_CLASSIFICATION"] == "NO_USEFUL_STRUCTURE"
    assert batch["D12_EXECUTED"] is True
    assert batch["D13_EXECUTED"] is True
    assert batch["INTERNAL_DISCOVERY_CARDS_EXECUTED"] == 10
    assert batch["INTERNAL_PROMISING_PROTOTYPES"] == 4
    assert batch["AUTOMATIC_SPRINT05"] is False
    assert batch["POST_SPRINT04_AUTOMATION_MATURITY_DECISION_REQUIRED"] is True
    assert batch["NEXT_UNIT"] == "POST_SPRINT04_AUTOMATION_MATURITY_DECISION"
    assert batch["SCIENTIFIC_OUTCOMES_COMPUTED"] is True
    assert batch["RERUN_AUTHORIZED"] is False
    assert batch["ONE_SHOT"] is True
    assert batch["D7_RERUN_PERFORMED"] is False
    assert batch["D8_EXECUTED"] is False
    assert batch["D7_CONFIRMATION_EXECUTED"] is False
    assert batch["D11_CONFIRMATION_EXECUTED"] is False
    assert batch["PROTECTED_2025_OPENED"] is False
    assert batch["PROTECTED_2026_OPENED"] is False
    assert batch["MARKET_07_CREATED"] is False
    assert batch["RESULT_PAYLOAD_SHA256"] == EX.payload_sha256(batch)
    assert batch["RESULT_PAYLOAD_SHA256"] == (
        "a70d7c4b9d84e6b5d3b1a1f27b514d5c725dda1f4c0ca7fa38180eb353064ddd"
    )
    assert batch["D12_RESULT_PAYLOAD_SHA256"] == (
        "73299c8d8313c7c73f423bb83565a45e3c17da6a534dbc8dc8fbf12f943b6feb"
    )
    assert batch["D13_RESULT_PAYLOAD_SHA256"] == (
        "c18f7de5821d8ee808732e0278afa53f622bb977d77f1ec71ee7423c96f5effd"
    )


def test_frozen_scientific_impl_not_mutated_by_result_commit():
    freeze = _load(FREEZE_PATH)
    assert C.implementation_hashes(REPO) == freeze["IMPLEMENTATION_HASHES"]
    assert "scripts/research/discovery_sprint_04/execute_scientific.py" not in freeze[
        "IMPLEMENTATION_HASHES"
    ]
