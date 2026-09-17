"""V3 reservation/execution plumbing tests. Disposable identities only.

These tests never execute world_index 10000..10399 and never create a live
canonical reservation, WORLD_RECORDS, or RESULT.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from scripts.research import harness_synthetic_edge_calibration_v3_authority as v3a
from scripts.research import harness_synthetic_edge_calibration_v3_production as v3p
from scripts.research.harness_synthetic_edge_calibration_v3_authority import (
    V3ExecutionNotAuthorized,
)
from scripts.research.harness_synthetic_edge_calibration_v3_confirmatory import V3WorldRecord

REPO = Path(__file__).resolve().parents[2]
_DISPOSABLE = 900_043


def _fake_record(scenario: str, world_index: int, *, detected: bool, valid: bool = True) -> V3WorldRecord:
    return V3WorldRecord(
        scenario=scenario,
        n_rows=5000,
        world_index=world_index,
        world_id=f"{scenario}|5000|{world_index}",
        feature_id="F03",
        world_valid=valid,
        detected=detected if valid else None,
        validity_guard_failed=None if valid else "SUPPORT_VALIDITY",
        validity_reason=None if valid else "fixture invalid",
        world_seed_int=world_index,
    )


def test_live_pre_reservation_authenticates_without_creating_reservation():
    if (REPO / v3a.CANONICAL_V3_RESERVATION_PATH).exists():
        pytest.skip("live reservation already exists")
    import subprocess

    status = subprocess.check_output(
        ["git", "-C", str(REPO), "status", "--porcelain", "--untracked-files=all"],
        text=True,
    )
    if status.strip():
        pytest.skip("worktree dirty; executed-byte gate is live-run only")
    status = v3p.authenticate_v3_pre_reservation()
    assert status["status"] == "V3_PRE_RESERVATION_AUTHENTICATED"
    assert status["run_identity"] == v3a.FROZEN_V3_RUN_IDENTITY
    assert status["authorization_consumed"] is False
    assert (REPO / v3a.CANONICAL_V3_RESERVATION_PATH).exists() is False


def test_live_reservation_document_binds_frozen_identity_without_writing():
    existed = (REPO / v3a.CANONICAL_V3_RESERVATION_PATH).exists()
    doc = v3p.v3_durable_reservation_document()
    assert doc["run_identity"] == v3a.FROZEN_V3_RUN_IDENTITY
    assert doc["arm_artifact_sha256"] == v3p.ARM_ARTIFACT_SHA256
    assert doc["canonical_world_count"] == 1600
    assert doc["world_index_start"] == 10000
    assert doc["world_index_end"] == 10399
    assert doc["bootstrap_replicates"] == 999
    assert doc["feature_id"] == "F03"
    assert doc["authorization_consumed"] is True
    assert doc["lifecycle"] == v3a.LIFECYCLE_RESERVED
    assert len(doc["reservation_identity"]) == 64
    assert (REPO / v3a.CANONICAL_V3_RESERVATION_PATH).exists() is existed


def test_caller_override_rejected():
    with pytest.raises(V3ExecutionNotAuthorized, match="caller arguments"):
        v3p.authenticate_v3_pre_reservation(B=1)
    with pytest.raises(V3ExecutionNotAuthorized, match="caller arguments"):
        v3a.reserve_v3_canonical_run(run_identity="forged")
    with pytest.raises(V3ExecutionNotAuthorized, match="caller arguments"):
        v3a.run_canonical_v3_grid(workers=8)


def test_mechanical_aggregates_use_frozen_wilson_boundaries():
    records = []
    for cell, detected_count in (
        ("EASY", 370),
        ("MODERATE", 296),
        ("NULL", 12),
        ("NONSTATIONARY_TRAP", 66),
    ):
        for i in range(400):
            records.append(
                _fake_record(cell, i, detected=i < detected_count)
            )
    aggregates = v3p.derive_v3_cell_aggregates(records)
    assert aggregates["EASY"]["verdict"] == "PASS"
    assert aggregates["MODERATE"]["verdict"] == "PASS"
    assert aggregates["NULL"]["verdict"] == "PASS"
    assert aggregates["NONSTATIONARY_TRAP"]["verdict"] == "PASS"
    conclusion = v3p.derive_v3_mechanical_conclusion(records)
    assert conclusion["methodology_claimable"] is True
    assert conclusion["incomplete_execution"] is False
    assert conclusion["default_v4"] is False
    assert conclusion["v3_rerun_authorized"] is False


def test_trap_93_is_indeterminate_not_fail():
    records = []
    for cell, detected_count in (
        ("EASY", 370),
        ("MODERATE", 296),
        ("NULL", 12),
        ("NONSTATIONARY_TRAP", 93),
    ):
        for i in range(400):
            records.append(_fake_record(cell, i, detected=i < detected_count))
    aggregates = v3p.derive_v3_cell_aggregates(records)
    assert aggregates["NONSTATIONARY_TRAP"]["verdict"] == "INDETERMINATE"


def test_incomplete_cell_is_not_claimable():
    records = [_fake_record("EASY", i, detected=True) for i in range(10)]
    conclusion = v3p.derive_v3_mechanical_conclusion(records)
    assert conclusion["incomplete_execution"] is True
    assert conclusion["methodology_claimable"] is False
    assert conclusion["final_mechanical_conclusion"] == "INCOMPLETE_EXECUTION_NO_METHODOLOGY_CLAIM"


def test_durable_store_roundtrip_disposable_record(tmp_path):
    record = _fake_record("EASY", _DISPOSABLE, detected=True)
    store = v3p.V3DurablePartialWorldStore.open(
        tmp_path / "store",
        run_identity=v3a.FROZEN_V3_RUN_IDENTITY,
        arm_commit="de7b38341c65eb82b66494d910fefd3395f8b232",
    )
    job = ("EASY", 5000, _DISPOSABLE)
    store.checkpoint_completed_world(record, job)
    loaded = store.load_structurally_valid_cached()
    assert job in loaded
    assert v3p._records_equivalent(loaded[job], record)


def test_second_reservation_fail_closed_when_artifact_present(tmp_path, monkeypatch):
    reservation = tmp_path / v3a.CANONICAL_V3_RESERVATION_PATH
    reservation.parent.mkdir(parents=True, exist_ok=True)
    reservation.write_text(json.dumps({"lifecycle": "RESERVED"}) + "\n", encoding="utf-8")
    monkeypatch.setattr(v3a, "_repo_root", lambda: tmp_path)
    monkeypatch.setattr(v3p, "_repo_root", lambda: tmp_path)
    with pytest.raises(V3ExecutionNotAuthorized):
        v3p.establish_v3_durable_reservation(tmp_path)


def test_mint_refuses_before_reservation():
    if (REPO / v3a.CANONICAL_V3_RESERVATION_PATH).exists():
        pytest.skip("live reservation already exists")
    with pytest.raises(V3ExecutionNotAuthorized, match="WORLD_RECORDS"):
        v3a.mint_v3_world_records()
    with pytest.raises(V3ExecutionNotAuthorized, match="RESULT"):
        v3a.mint_v3_result()
    assert (REPO / v3a.CANONICAL_V3_WORLD_RECORDS_PATH).exists() is False
    assert (REPO / v3a.CANONICAL_V3_RESULT_PATH).exists() is False


def test_production_tests_do_not_evaluate_canonical_world_indices():
    v3a.assert_index_not_canonical(_DISPOSABLE)
    source = Path(__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    called = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Name):
            called.add(func.id)
        elif isinstance(func, ast.Attribute):
            called.add(func.attr)
    assert "evaluate_v3_world" not in called
    assert "simulate_dgp" not in called
    assert "execute_canonical_v3_production" not in called
    assert "run_canonical_v3_grid_in_session" not in called
    assert "establish_v3_durable_reservation" in called
