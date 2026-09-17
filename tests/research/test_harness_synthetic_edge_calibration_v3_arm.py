"""One-shot V3 ARM tests. Disposable identities only.

These tests never reserve the canonical run, never execute world_index
10000..10399, and never mint WORLD_RECORDS or RESULT.
"""

from __future__ import annotations

import ast
import json
import subprocess
from pathlib import Path

import pytest

from scripts.research import harness_synthetic_edge_calibration_v3_authority as v3a
from scripts.research.harness_synthetic_edge_calibration_v3_authority import (
    V3ExecutionNotAuthorized,
    V3NotArmed,
)

REPO = Path(__file__).resolve().parents[2]
FREEZE_HEAD = v3a.IMPLEMENTATION_FREEZE_HEAD
FREEZE_TREE = v3a.IMPLEMENTATION_FREEZE_TREE
EXPECTED_RID = v3a.FROZEN_V3_RUN_IDENTITY
_DISPOSABLE = 900_042


def _git(*args: str, repo: Path = REPO) -> str:
    return subprocess.check_output(["git", "-C", str(repo), *args], text=True).strip()


def _write(path: Path, data: bytes | str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(data, str):
        path.write_text(data, encoding="utf-8")
    else:
        path.write_bytes(data)


def _copy_live(rel: str, dest_root: Path) -> None:
    _write(dest_root / rel, (REPO / rel).read_bytes())


def _bind(monkeypatch, repo: Path) -> None:
    monkeypatch.setattr(v3a, "_repo_root", lambda: repo)


def _commit_freeze_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git("init", repo=repo)
    _git("config", "user.email", "test@example.com", repo=repo)
    _git("config", "user.name", "test", repo=repo)
    _git("config", "commit.gpgsign", "false", repo=repo)
    for rel in (
        v3a.CONFIRMATORY_REL,
        v3a.RNG_REL,
        v3a.V1_LIB_REL,
        v3a.CANONICAL_PREREG_MD_PATH,
        v3a.CANONICAL_PREREG_JSON_PATH,
        v3a.CANONICAL_FREEZE_JSON_PATH,
        v3a.CANONICAL_FREEZE_MD_PATH,
        v3a.CONFIRMATORY_TESTS_REL,
        v3a.RNG_TESTS_REL,
    ):
        _copy_live(rel, repo)
    _git("add", "-A", repo=repo)
    _git("commit", "-m", "v3 freeze parent", repo=repo)
    return repo


def _arm_payload(repo: Path) -> dict:
    return v3a.required_v3_arm_binding_fields()


def _commit_arm(repo: Path, payload: dict | None = None) -> str:
    body = payload if payload is not None else _arm_payload(repo)
    _write(
        repo / v3a.CANONICAL_V3_ARM_PATH,
        json.dumps(body, sort_keys=True, indent=2, ensure_ascii=False) + "\n",
    )
    _git("add", v3a.CANONICAL_V3_ARM_PATH, repo=repo)
    _git("commit", "-m", "v3 arm", repo=repo)
    return _git("rev-parse", "HEAD", repo=repo)


def test_live_arm_authenticates_exact_frozen_run_identity():
    if v3a.CANONICAL_V3_ARM_PATH not in _git("ls-tree", "-r", "--name-only", "HEAD"):
        pytest.skip("live ARM not yet committed")
    bound = v3a.authenticate_v3_arm()
    assert bound["run_identity"] == EXPECTED_RID
    assert bound["freeze_parent_head"] == FREEZE_HEAD
    assert bound["freeze_parent_tree"] == FREEZE_TREE
    assert bound["lifecycle"] == v3a.LIFECYCLE_AUTHORIZED_UNUSED
    assert bound["authorization_consumed"] is False
    assert v3a.v3_arm_authorized() is True
    state = v3a.inspect_v3_authorization_state()
    assert state["lifecycle"] == v3a.LIFECYCLE_AUTHORIZED_UNUSED
    assert state["v3_armed"] is True
    assert state["v3_run_authorized"] is True
    assert state["authorization_consumed"] is False
    assert state["reservation_created"] is False
    payload = json.loads((REPO / v3a.CANONICAL_V3_ARM_PATH).read_text(encoding="utf-8"))
    assert payload["run_identity"] == EXPECTED_RID
    assert payload["freeze_parent_head"] == FREEZE_HEAD
    assert payload["reviewed_implementation_head"] == v3a.ACCEPTED_IMPLEMENTATION_HEAD
    assert payload["lifecycle"] == v3a.LIFECYCLE_AUTHORIZED_UNUSED
    assert payload["authorization_consumed"] is False


def test_wrong_run_identity_rejected(tmp_path, monkeypatch):
    repo = _commit_freeze_repo(tmp_path)
    _bind(monkeypatch, repo)
    payload = _arm_payload(repo)
    payload["run_identity"] = "0" * 64
    payload["canonical_v3_plan_sha256"] = "0" * 64
    _commit_arm(repo, payload)
    with pytest.raises(V3ExecutionNotAuthorized, match="run_identity"):
        v3a.authenticate_v3_arm()
    assert v3a.v3_arm_authorized() is False


def test_wrong_implementation_freeze_head_tree_rejected(tmp_path, monkeypatch):
    repo = _commit_freeze_repo(tmp_path)
    _bind(monkeypatch, repo)
    payload = _arm_payload(repo)
    payload["freeze_parent_head"] = "0" * 40
    _commit_arm(repo, payload)
    with pytest.raises(V3ExecutionNotAuthorized, match="freeze_parent_head"):
        v3a.authenticate_v3_arm()
    payload = json.loads((repo / v3a.CANONICAL_V3_ARM_PATH).read_text(encoding="utf-8"))
    payload["freeze_parent_head"] = _git("rev-parse", "HEAD^", repo=repo)
    payload["freeze_parent_tree"] = "0" * 40
    _write(repo / v3a.CANONICAL_V3_ARM_PATH, json.dumps(payload, indent=2) + "\n")
    _git("add", v3a.CANONICAL_V3_ARM_PATH, repo=repo)
    _git("commit", "--amend", "--no-edit", repo=repo)
    with pytest.raises(V3ExecutionNotAuthorized, match="freeze_parent_tree"):
        v3a.authenticate_v3_arm()


def test_scientific_byte_mutation_rejected(tmp_path, monkeypatch):
    repo = _commit_freeze_repo(tmp_path)
    _bind(monkeypatch, repo)
    _commit_arm(repo)
    v3a.authenticate_v3_arm()
    target = repo / v3a.CONFIRMATORY_REL
    target.write_bytes(target.read_bytes() + b"\n# mutated\n")
    _git("add", v3a.CONFIRMATORY_REL, repo=repo)
    _git("commit", "-m", "mutate confirmatory", repo=repo)
    with pytest.raises(V3ExecutionNotAuthorized, match="scientific"):
        v3a.authenticate_v3_arm()


def test_canonical_grid_mutation_rejected(tmp_path, monkeypatch):
    repo = _commit_freeze_repo(tmp_path)
    _bind(monkeypatch, repo)
    payload = _arm_payload(repo)
    payload["canonical_world_count"] = 3200
    _commit_arm(repo, payload)
    with pytest.raises(
        V3ExecutionNotAuthorized, match="literal mismatch|canonical-grid|canonical_world_count"
    ):
        v3a.authenticate_v3_arm()


def test_caller_scientific_override_rejected(tmp_path, monkeypatch):
    repo = _commit_freeze_repo(tmp_path)
    _bind(monkeypatch, repo)
    _commit_arm(repo)
    with pytest.raises(V3ExecutionNotAuthorized, match="caller arguments"):
        v3a.authenticate_v3_arm(run_identity="forged")
    with pytest.raises(V3ExecutionNotAuthorized, match="caller arguments"):
        v3a.inspect_v3_reservation_readiness(grid={"B": 1})
    monkeypatch.setenv("HARNESS_V3_PREREG_PATH", "/tmp/evil.json")
    with pytest.raises(V3ExecutionNotAuthorized, match="environment substitution"):
        v3a.authenticate_v3_arm()


def test_arm_begins_unused_and_validation_does_not_consume(tmp_path, monkeypatch):
    repo = _commit_freeze_repo(tmp_path)
    _bind(monkeypatch, repo)
    _commit_arm(repo)
    first = v3a.authenticate_v3_arm()
    second = v3a.authenticate_v3_arm()
    assert first["lifecycle"] == v3a.LIFECYCLE_AUTHORIZED_UNUSED
    assert second["lifecycle"] == v3a.LIFECYCLE_AUTHORIZED_UNUSED
    assert first["authorization_consumed"] is False
    assert second["authorization_consumed"] is False
    assert v3a.v3_arm_authorized() is True
    assert (repo / v3a.CANONICAL_V3_RESERVATION_PATH).exists() is False
    assert v3a.v3_protected_artifacts_present() is False


def test_disposable_execution_cannot_consume_canonical_authorization(tmp_path, monkeypatch):
    repo = _commit_freeze_repo(tmp_path)
    _bind(monkeypatch, repo)
    _commit_arm(repo)
    with pytest.raises(V3ExecutionNotAuthorized, match="reservation"):
        v3a.evaluate_v3_canonical_world("EASY", 5000, 10000)
    with pytest.raises(V3ExecutionNotAuthorized, match="reservation"):
        v3a.run_canonical_v3_grid()
    v3a.assert_index_not_canonical(_DISPOSABLE)
    state = v3a.inspect_v3_authorization_state()
    assert state["authorization_consumed"] is False
    assert state["lifecycle"] == v3a.LIFECYCLE_AUTHORIZED_UNUSED


def test_reservation_path_recognizes_unused_arm_without_creating_reservation(
    tmp_path, monkeypatch
):
    repo = _commit_freeze_repo(tmp_path)
    _bind(monkeypatch, repo)
    _commit_arm(repo)
    ready = v3a.inspect_v3_reservation_readiness()
    assert ready["arm_authentic"] is True
    assert ready["authorization_unused"] is True
    assert ready["reservation_created"] is False
    assert ready["ready_for_reservation"] is True
    assert ready["run_identity"] == v3a.derive_v3_run_identity()
    assert (repo / v3a.CANONICAL_V3_RESERVATION_PATH).exists() is False
    with pytest.raises(V3ExecutionNotAuthorized, match="does not create a canonical V3 reservation"):
        v3a.reserve_v3_canonical_run()
    assert (repo / v3a.CANONICAL_V3_RESERVATION_PATH).exists() is False
    assert v3a.v3_arm_authorized() is True


def test_second_consumption_semantics_fail_closed_in_fixture(tmp_path, monkeypatch):
    repo = _commit_freeze_repo(tmp_path)
    _bind(monkeypatch, repo)
    _commit_arm(repo)
    reservation = {
        "schema": "harness_synthetic_edge_calibration_v3_production_reservation",
        "lifecycle": v3a.LIFECYCLE_RESERVED,
        "run_identity": v3a.derive_v3_run_identity(),
        "authorization_consumed": True,
    }
    _write(repo / v3a.CANONICAL_V3_RESERVATION_PATH, json.dumps(reservation, indent=2) + "\n")
    _git("add", v3a.CANONICAL_V3_RESERVATION_PATH, repo=repo)
    _git("commit", "-m", "fixture reservation consumption", repo=repo)
    with pytest.raises(V3ExecutionNotAuthorized, match="consumed"):
        v3a.authenticate_v3_arm()
    assert v3a.v3_arm_authorized() is False
    state = v3a.inspect_v3_authorization_state()
    assert state["authorization_consumed"] is True
    assert state["v3_armed"] is False
    with pytest.raises(V3NotArmed):
        v3a.run_canonical_v3_grid()


def test_world_records_and_result_remain_impossible_before_reservation(tmp_path, monkeypatch):
    repo = _commit_freeze_repo(tmp_path)
    _bind(monkeypatch, repo)
    _commit_arm(repo)
    with pytest.raises(V3ExecutionNotAuthorized, match="WORLD_RECORDS"):
        v3a.mint_v3_world_records()
    with pytest.raises(V3ExecutionNotAuthorized, match="RESULT"):
        v3a.mint_v3_result()
    assert (repo / v3a.CANONICAL_V3_WORLD_RECORDS_PATH).exists() is False
    assert (repo / v3a.CANONICAL_V3_RESULT_PATH).exists() is False


def test_arm_tests_do_not_evaluate_canonical_world_indices():
    v3a.assert_index_not_canonical(_DISPOSABLE)
    with pytest.raises(V3ExecutionNotAuthorized, match="canonical world indices"):
        v3a.assert_index_not_canonical(10000)
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
    assert "evaluate_v3_canonical_world" in called
