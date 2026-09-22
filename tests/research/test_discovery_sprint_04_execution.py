"""Outcome-blind Sprint 04 one-shot permit/runner tests. No scientific outcomes."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.research.discovery_sprint_04 import common as C
from scripts.research.discovery_sprint_04 import execute_scientific as EX
from scripts.research.discovery_sprint_04 import evaluate as E
from scripts.research.discovery_sprint_04 import d13_panel as P

REPO = Path(__file__).resolve().parents[2]
PERMIT = REPO / EX.PERMIT_REL
FREEZE = REPO / EX.FREEZE_REL


def test_common_execution_authorized_remains_false():
    assert C.EXECUTION_AUTHORIZED is False


def test_evaluate_module_still_refuses_without_global_flag():
    with pytest.raises(C.RealScientificOutcomeForbidden):
        E.evaluate_d12_real()
    with pytest.raises(C.RealScientificOutcomeForbidden):
        E.evaluate_d13_real()
    with pytest.raises(C.RealScientificOutcomeForbidden):
        E.evaluate_supplied_arrays("D12", support={"IDENTITY_OK": True}, us_a=[0.1])
    with pytest.raises(C.RealScientificOutcomeForbidden):
        P.load_price_panel_real()


def test_runner_refuses_without_authorize_flag():
    with pytest.raises(C.RealScientificOutcomeForbidden, match="SPRINT04_EXECUTION_NOT_AUTHORIZED"):
        EX.execute(repo=REPO, authorize=False, write=False)


def test_permit_binds_execution_root_and_frozen_identities():
    permit = json.loads(PERMIT.read_text(encoding="utf-8"))
    freeze = json.loads(FREEZE.read_text(encoding="utf-8"))
    assert permit["EXECUTION_ROOT"] == EX.EXECUTION_ROOT == "d2a62da6e5c907def603a258505b9cc1f92ae3a5"
    assert permit["EXPECTED_TREE"] == EX.EXPECTED_TREE == "3c5c5262db5c1313c8d5c712c0d1658f32da0edb"
    assert permit["ONE_SHOT"] is True
    assert permit["RERUN_AUTHORIZED"] is False
    assert permit["SCIENTIFIC_OUTCOMES_COMPUTED"] is False
    assert permit["EXECUTION_AUTHORIZED_IN_COMMON_PY"] is False
    assert permit["D12_RANDOM_SEED"] == 20260922196
    assert permit["D13_RANDOM_SEED"] == 20260922197
    assert permit["D13_N"] == 82
    assert permit["D13_SNAPSHOT_ID"] == freeze["D13_SNAPSHOT_ID"]
    assert permit["D13_FILE_LEDGER_DIGEST"] == freeze["D13_FILE_LEDGER_DIGEST"]
    assert permit["D13_UNIVERSE_IDENTITY_DIGEST"] == freeze["D13_UNIVERSE_IDENTITY_DIGEST"]
    assert permit["D13_EXCLUSION_LIST_DIGEST"] == freeze["D13_EXCLUSION_LIST_DIGEST"]
    assert permit["D13_PINNED_TAKER_FEE"] == 0.001
    assert permit["D13_FRICTION_FLOOR"] == 0.004
    assert permit["D13_RUNTIME_FILE_AUTHORITY"] == "SNAPSHOT_BOUND_OBJECT_LEDGER"
    assert permit["IMPLEMENTATION_HASHES"] == freeze["IMPLEMENTATION_HASHES"]
    assert permit["IMPLEMENTATION_HASHES"] == C.implementation_hashes(REPO)
    assert permit["IMPLEMENTATION_FREEZE_SHA256"] == C.sha256_file(FREEZE)
    assert permit["ONE_SHOT_RUNNER_SHA256"] == C.sha256_file(REPO / EX.RUNNER_REL)
    hashed = {k: v for k, v in permit.items() if k != "PERMIT_SHA256"}
    recomputed = C.sha256_bytes(
        json.dumps(hashed, indent=2, sort_keys=True, ensure_ascii=False).encode("utf-8") + b"\n"
    )
    assert permit["PERMIT_SHA256"] == recomputed


def test_close_panel_loader_uses_ledger_not_index():
    import inspect

    text = inspect.getsource(EX.load_close_panel_from_ledger)
    assert "scientific_file_keys" in text
    assert "legal_zips" not in text
    assert "object_key_index" not in text


def test_eu_diagnostic_flag_is_hard_false_in_builder():
    import inspect

    text = inspect.getsource(EX.build_d12_result)
    assert "EU_DIAGNOSTIC_AFFECTS_CLASSIFICATION" in text
    assert "False" in text
