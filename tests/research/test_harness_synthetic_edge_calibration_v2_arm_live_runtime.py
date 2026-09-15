"""Live-runtime byte binding regressions for V2 session execution.

Reproduces the independently reviewed session-path attack: legitimate Git
authority with a caller-supplied repo_root must not execute imported
production bytes from a different tree. These tests must not create a real
ARM in project history, consume a real reservation, run the canonical
3200-world grid, or mint RESULT/WORLD_RECORDS.
"""

from __future__ import annotations

import importlib.util
import inspect
import sys
from pathlib import Path
from unittest import mock

import pytest

from scripts.research import harness_synthetic_edge_calibration_v2_inherited_ladder as ladder
from scripts.research import harness_synthetic_edge_calibration_v2_production as v2p
from tests.research.test_harness_synthetic_edge_calibration_v2_production import (
    _patch_loaded_runtime_to_commit,
    _v2_commit_arm,
    _v2_commit_freeze_tree,
    _v2_valid_arm_payload,
    _write,
)

REPO = Path(__file__).resolve().parents[2]


def _armed_reserved_clone(tmp_path: Path):
    repo = _v2_commit_freeze_tree(tmp_path)
    payload = _v2_valid_arm_payload(repo)
    arm_commit = _v2_commit_arm(repo, payload)
    v2p.establish_v2_durable_reservation(repo, arm_commit)
    return repo, arm_commit


def test_assert_executed_runtime_has_no_repo_root_skip():
    src = inspect.getsource(v2p._assert_executed_runtime_bound_to_commit)
    assert "live_root" not in src
    assert "!= live_root" not in src
    assert "return\n" not in src.replace(" ", "")


def test_1_legit_authority_tampered_imported_production_refuses(tmp_path):
    repo, arm_commit = _armed_reserved_clone(tmp_path)
    tampered_path = tmp_path / "tampered_production.py"
    tampered_path.write_bytes(Path(v2p.__file__).read_bytes() + b"\n# TAMPERED LIVE PRODUCTION\n")
    spec = importlib.util.spec_from_file_location(
        "tampered_v2_production_runtime", tampered_path
    )
    tampered = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules["tampered_v2_production_runtime"] = tampered
    spec.loader.exec_module(tampered)
    executed = {"evaluate": False}

    def boom(*_args, **_kwargs):
        executed["evaluate"] = True
        raise AssertionError("tampered scientific path must not run")

    tampered._production_evaluate_one_world = boom
    with pytest.raises(tampered.SyntheticExecutionNotAuthorized):
        tampered.open_v2_production_session(repo_root=repo, arm_commit=arm_commit)
    assert executed["evaluate"] is False


def test_1_session_execution_refuses_when_live_production_bytes_differ(tmp_path, monkeypatch):
    repo, arm_commit = _armed_reserved_clone(tmp_path)
    small = tuple(v2p.canonical_v2_production_jobs()[:1])
    _patch_loaded_runtime_to_commit(monkeypatch, repo, arm_commit)
    with mock.patch.object(v2p, "canonical_v2_production_jobs", return_value=small):
        session = v2p.open_v2_production_session(repo_root=repo, arm_commit=arm_commit)
        blobs = v2p._loaded_runtime_bytes()
        blobs[v2p.V2_PRODUCTION_REL] = blobs[v2p.V2_PRODUCTION_REL] + b"\n# TAMPER\n"
        monkeypatch.setattr(v2p, "_loaded_runtime_bytes", lambda: blobs)
        executed = {"evaluate": False}

        def boom(*_args, **_kwargs):
            executed["evaluate"] = True
            raise AssertionError("tampered production must not evaluate")

        monkeypatch.setattr(v2p, "_production_evaluate_one_world", boom)
        with pytest.raises(v2p.SyntheticExecutionNotAuthorized, match="loaded runtime bytes"):
            v2p.evaluate_v2_world_in_session(session, *small[0])
        assert executed["evaluate"] is False


def test_2_tampered_inherited_ladder_live_module_refuses(tmp_path, monkeypatch):
    repo, arm_commit = _armed_reserved_clone(tmp_path)
    small = tuple(v2p.canonical_v2_production_jobs()[:1])
    prod_blob = v2p._commit_blob(repo, arm_commit, v2p.V2_PRODUCTION_REL)
    ladder_blob = v2p._commit_blob(repo, arm_commit, v2p.V2_INHERITED_LADDER_REL)
    assert prod_blob is not None and ladder_blob is not None
    monkeypatch.setattr(
        v2p,
        "_loaded_runtime_bytes",
        lambda: {
            v2p.V2_PRODUCTION_REL: prod_blob,
            v2p.V2_INHERITED_LADDER_REL: ladder_blob + b"\n# TAMPERED LADDER\n",
        },
    )
    with mock.patch.object(v2p, "canonical_v2_production_jobs", return_value=small):
        with pytest.raises(v2p.SyntheticExecutionNotAuthorized, match="loaded runtime bytes"):
            v2p.open_v2_production_session(repo_root=repo, arm_commit=arm_commit)


def test_3_repo_root_mismatch_does_not_skip_live_binding(tmp_path):
    repo, arm_commit = _armed_reserved_clone(tmp_path)
    live_root = Path(v2p.__file__).resolve().parents[2]
    assert Path(repo).resolve() != live_root
    with pytest.raises(v2p.SyntheticExecutionNotAuthorized, match="loaded runtime bytes"):
        v2p._assert_executed_runtime_bound_to_commit(repo, arm_commit)
    with pytest.raises(v2p.SyntheticExecutionNotAuthorized, match="loaded runtime bytes"):
        v2p.open_v2_production_session(repo_root=repo, arm_commit=arm_commit)


def test_4_session_recheck_refuses_evaluate_after_runtime_mutation(tmp_path, monkeypatch):
    repo, arm_commit = _armed_reserved_clone(tmp_path)
    small = tuple(v2p.canonical_v2_production_jobs()[:1])
    _patch_loaded_runtime_to_commit(monkeypatch, repo, arm_commit)
    with mock.patch.object(v2p, "canonical_v2_production_jobs", return_value=small):
        session = v2p.open_v2_production_session(repo_root=repo, arm_commit=arm_commit)
        blobs = dict(v2p._loaded_runtime_bytes())
        blobs[v2p.V2_PRODUCTION_REL] = blobs[v2p.V2_PRODUCTION_REL] + b"\n# AFTER SESSION\n"
        monkeypatch.setattr(v2p, "_loaded_runtime_bytes", lambda: blobs)
        with pytest.raises(v2p.SyntheticExecutionNotAuthorized, match="loaded runtime bytes"):
            v2p.evaluate_v2_world_in_session(session, *small[0])


def test_4_session_recheck_refuses_grid_after_runtime_mutation(tmp_path, monkeypatch):
    repo, arm_commit = _armed_reserved_clone(tmp_path)
    small = tuple(v2p.canonical_v2_production_jobs()[:1])
    _patch_loaded_runtime_to_commit(monkeypatch, repo, arm_commit)
    with mock.patch.object(v2p, "canonical_v2_production_jobs", return_value=small):
        session = v2p.open_v2_production_session(repo_root=repo, arm_commit=arm_commit)
        blobs = dict(v2p._loaded_runtime_bytes())
        blobs[v2p.V2_INHERITED_LADDER_REL] = (
            blobs[v2p.V2_INHERITED_LADDER_REL] + b"\n# AFTER SESSION LADDER\n"
        )
        monkeypatch.setattr(v2p, "_loaded_runtime_bytes", lambda: blobs)
        with pytest.raises(v2p.SyntheticExecutionNotAuthorized, match="loaded runtime bytes"):
            v2p.run_canonical_v2_production_grid_in_session(session)


def test_5_matching_live_runtime_still_allows_session_execution(tmp_path, monkeypatch):
    repo, arm_commit = _armed_reserved_clone(tmp_path)
    small = tuple(v2p.canonical_v2_production_jobs()[:1])
    _patch_loaded_runtime_to_commit(monkeypatch, repo, arm_commit)
    with mock.patch.object(v2p, "canonical_v2_production_jobs", return_value=small):
        session = v2p.open_v2_production_session(repo_root=repo, arm_commit=arm_commit)
        rec = v2p.evaluate_v2_world_in_session(session, *small[0])
        assert rec.scenario == small[0][0]
        records = v2p.run_canonical_v2_production_grid_in_session(session)
        assert len(records) == 1
        assert records[0] == rec


def test_live_head_bytes_still_match_imported_modules():
    loaded = v2p._loaded_runtime_bytes()
    assert loaded[v2p.V2_PRODUCTION_REL] == Path(v2p.__file__).read_bytes()
    assert loaded[v2p.V2_INHERITED_LADDER_REL] == Path(ladder.__file__).read_bytes()
    head_blob = v2p._commit_blob(REPO, "HEAD", v2p.V2_PRODUCTION_REL)
    if head_blob != loaded[v2p.V2_PRODUCTION_REL]:
        pytest.skip("worktree production.py differs from HEAD before the repair commit")
    v2p._assert_executed_runtime_bound_to_commit(REPO, "HEAD")
