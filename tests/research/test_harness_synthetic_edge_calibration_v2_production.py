"""Tests for the V2 production driver, canonical plan, and ARM runtime authorization.

Disposable temporary git repositories and tiny synthetic worlds only. These
tests must not run the frozen 3200-world Monte Carlo, mint RESULT/WORLD_RECORDS,
create a real ARM in project history, or consume V1/V2 authority.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

from scripts.research import harness_synthetic_edge_calibration_v1_lib as lib
from scripts.research import harness_synthetic_edge_calibration_v1_production as prod
from scripts.research import harness_synthetic_edge_calibration_v2_production as v2p
from scripts.research import harness_synthetic_edge_calibration_v2_rank_policy as v2

REPO = Path(__file__).resolve().parents[2]


def _git(repo: Path, *args: str) -> str:
    import subprocess

    proc = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=True,
    )
    return proc.stdout.strip()


def _write(path: Path, data: bytes | str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(data, str):
        path.write_text(data, encoding="utf-8")
    else:
        path.write_bytes(data)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _live_bytes(rel: str) -> bytes:
    return (REPO / rel).read_bytes()


# --- Part A: production per-world path is mechanically equivalent to the ----
# --- frozen fixture's own public API (no reimplemented classification). -----


def _worlds_for_equivalence():
    scenarios = [s["id"] for s in lib.load_frozen_prereg()["scenarios"]]
    for scenario in scenarios:
        for n_rows in (50, 100, 250):
            for world_index in range(4):
                yield scenario, n_rows, world_index


def test_production_per_world_matches_fixture_public_api_exhaustively():
    checked = 0
    for scenario, n_rows, world_index in _worlds_for_equivalence():
        world = lib.simulate_dgp(scenario_id=scenario, n_rows=n_rows, world_index=world_index)
        expected = v2.evaluate_v2_world(world, scenario=scenario, n_rows=n_rows, world_index=world_index)
        actual = v2p._production_evaluate_one_world(
            world, scenario=scenario, n_rows=n_rows, world_index=world_index
        )
        assert actual == expected
        checked += 1
    assert checked >= 6 * 3 * 4


def test_production_per_world_matches_fixture_on_forced_lookahead(monkeypatch):
    def boom(*_args, **_kwargs):
        raise lib.IncompleteWorld("lookahead: future era entered earlier fit")

    world = lib.simulate_dgp(scenario_id="EASY", n_rows=50, world_index=0)
    monkeypatch.setattr(v2, "expanding_era_predictions", boom)
    expected = v2.evaluate_v2_world(world, scenario="EASY", n_rows=50, world_index=0)
    actual = v2p._production_evaluate_one_world(world, scenario="EASY", n_rows=50, world_index=0)
    assert expected.world_state == v2.WORLD_INVALID
    assert actual == expected


def test_production_per_world_never_uses_fixture_only_injections():
    # The production path must never force a reason/candidate; it always
    # calls the frozen inner function with neutral (no-injection) defaults.
    source = __import__("inspect").getsource(v2p._production_evaluate_one_world)
    assert "force_candidate_reason=None" in source
    assert "force_selected_candidate=None" in source
    assert "zero_e1_baseline=False" in source
    assert "zero_e1_features=frozenset()" in source


# --- Part B: canonical plan / job derivation ---------------------------------


def test_canonical_v2_jobs_are_exactly_v1_frozen_planned_jobs():
    jobs = v2p.canonical_v2_production_jobs()
    assert jobs == prod.planned_production_jobs()
    assert len(jobs) == 3200
    assert jobs[0] == ("NULL", 5000, 0)
    assert jobs[-1] == ("SMALL", 10000, 399)


def test_canonical_v2_world_count_is_3200():
    assert v2p.canonical_v2_world_count() == 3200


def test_canonical_v2_plan_is_deterministic():
    a = v2p.canonical_v2_plan()
    b = v2p.canonical_v2_plan()
    assert a == b
    assert a["payload"] == b["payload"]


def test_canonical_v2_plan_changes_if_v2_policy_identity_changes(tmp_path):
    repo = _v2_commit_freeze_tree(tmp_path)
    baseline = v2p.canonical_v2_plan(repo_root=repo, commit="HEAD")
    policy_path = repo / v2p.V2_POLICY_REL
    mutated = policy_path.read_bytes() + b"\n# mutated for test\n"
    _write(policy_path, mutated)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "mutate v2 policy")
    mutated_plan = v2p.canonical_v2_plan(repo_root=repo, commit="HEAD")
    assert mutated_plan["sha256"] != baseline["sha256"]


def test_canonical_v2_plan_changes_if_v1_grid_identity_changes(monkeypatch):
    baseline = v2p.canonical_v2_plan()

    def fake_grid():
        real = prod.frozen_production_grid()
        mutated = dict(real)
        mutated["root_seed"] = int(real["root_seed"]) + 1
        return mutated

    monkeypatch.setattr(v2p, "frozen_production_grid", fake_grid)
    mutated_plan = v2p.canonical_v2_plan()
    assert mutated_plan["sha256"] != baseline["sha256"]


# --- Part C: disposable-repo ARM authorization matrix ------------------------


def _v2_commit_freeze_tree(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir(parents=True)
    _git(repo, "init")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "test")
    _git(repo, "config", "commit.gpgsign", "false")
    copies = {
        "scripts/__init__.py": _live_bytes("scripts/__init__.py"),
        "scripts/research/__init__.py": _live_bytes("scripts/research/__init__.py"),
        prod.LIB_REL: _live_bytes(prod.LIB_REL),
        prod.RUNNER_REL: _live_bytes(prod.RUNNER_REL),
        prod.AUTH_REL: _live_bytes(prod.AUTH_REL),
        prod.PRODUCTION_REL: _live_bytes(prod.PRODUCTION_REL),
        prod.WORKER_REL: _live_bytes(prod.WORKER_REL),
        v2p.V2_POLICY_REL: _live_bytes(v2p.V2_POLICY_REL),
        v2p.V2_FREEZE_ARTIFACT_REL: _live_bytes(v2p.V2_FREEZE_ARTIFACT_REL),
        "docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1_PREREG.json": _live_bytes(
            "docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1_PREREG.json"
        ),
        "docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1_PREREG.md": _live_bytes(
            "docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1_PREREG.md"
        ),
    }
    for rel, data in copies.items():
        _write(repo / rel, data)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "v2 policy freeze tree")
    return repo


def _v2_valid_arm_payload(repo: Path) -> dict:
    parent = _git(repo, "rev-parse", "HEAD")
    parent_tree = _git(repo, "rev-parse", "HEAD^{tree}")
    freeze_blob = (repo / v2p.V2_FREEZE_ARTIFACT_REL).read_bytes()
    policy_blob = (repo / v2p.V2_POLICY_REL).read_bytes()
    plan = v2p.canonical_v2_plan(repo_root=repo, commit="HEAD")
    payload = dict(v2p.V2_ARM_REQUIRED_LITERALS)
    payload.update(
        {
            "freeze_parent_head": parent,
            "freeze_parent_tree": parent_tree,
            "freeze_artifact_sha256": _sha(freeze_blob),
            "freeze_artifact_size": len(freeze_blob),
            "v2_policy_sha256": _sha(policy_blob),
            "v2_policy_size": len(policy_blob),
            "canonical_v2_plan_sha256": plan["sha256"],
            "canonical_world_count": v2p.canonical_v2_world_count(),
            "original_prereg_head": v2p.FROZEN_ORIGINAL_PREREG_HEAD,
            "original_prereg_tree": v2p.FROZEN_ORIGINAL_PREREG_TREE,
            "amendment_001_head": v2p.FROZEN_AMENDMENT_001_HEAD,
            "amendment_001_tree": v2p.FROZEN_AMENDMENT_001_TREE,
        }
    )
    return payload


def _v2_commit_arm(repo: Path, payload: dict, *, message: str = "v2 production arm") -> str:
    _write(repo / v2p.CANONICAL_V2_ARM_PATH, json.dumps(payload, indent=2, sort_keys=True) + "\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", message)
    return _git(repo, "rev-parse", "HEAD")


def test_real_child_arm_authorizes_at_exact_arm_head(tmp_path):
    repo = _v2_commit_freeze_tree(tmp_path)
    payload = _v2_valid_arm_payload(repo)
    _v2_commit_arm(repo, payload)
    assert v2p.v2_production_arm_authorized(repo_root=repo) is True


def test_freeze_itself_does_not_authorize(tmp_path):
    repo = _v2_commit_freeze_tree(tmp_path)
    # HEAD is the freeze commit; no ARM file has been committed at all.
    assert v2p.v2_production_arm_authorized(repo_root=repo) is False


def test_descendant_of_arm_does_not_authorize(tmp_path):
    repo = _v2_commit_freeze_tree(tmp_path)
    payload = _v2_valid_arm_payload(repo)
    _v2_commit_arm(repo, payload)
    assert v2p.v2_production_arm_authorized(repo_root=repo) is True
    # A further commit's parent is the ARM, not the freeze.
    _write(repo / "docs/NOTE.md", "descendant\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "descendant of arm")
    assert v2p.v2_production_arm_authorized(repo_root=repo) is False


def test_sibling_without_arm_file_does_not_authorize(tmp_path):
    repo = _v2_commit_freeze_tree(tmp_path)
    payload = _v2_valid_arm_payload(repo)
    _v2_commit_arm(repo, payload)
    real_arm = _git(repo, "rev-parse", "HEAD")
    freeze = _git(repo, "rev-parse", f"{real_arm}^")
    _git(repo, "checkout", "-q", freeze)
    _write(repo / "docs/NOTE.md", "sibling, no arm\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "sibling of arm, no arm file")
    assert v2p.v2_production_arm_authorized(repo_root=repo) is False


def test_sibling_with_wrong_plan_hash_does_not_authorize(tmp_path):
    repo = _v2_commit_freeze_tree(tmp_path)
    freeze = _git(repo, "rev-parse", "HEAD")
    payload = _v2_valid_arm_payload(repo)
    payload["canonical_v2_plan_sha256"] = "0" * 64
    _v2_commit_arm(repo, payload, message="sibling arm with wrong plan hash")
    assert v2p.v2_production_arm_authorized(repo_root=repo) is False


@pytest.mark.parametrize(
    "field,value",
    [
        ("freeze_artifact_sha256", "0" * 64),
        ("v2_policy_sha256", "0" * 64),
        ("canonical_v2_plan_sha256", "0" * 64),
        ("canonical_world_count", 1),
        ("freeze_parent_head", "0" * 40),
        ("freeze_parent_tree", "0" * 40),
        ("original_prereg_head", "0" * 40),
        ("amendment_001_head", "0" * 40),
        ("authorization_consumed", True),
        ("status", "SOMETHING_ELSE"),
    ],
)
def test_mutated_arm_field_does_not_authorize(tmp_path, field, value):
    repo = _v2_commit_freeze_tree(tmp_path)
    payload = _v2_valid_arm_payload(repo)
    payload[field] = value
    _v2_commit_arm(repo, payload, message=f"mutated {field}")
    assert v2p.v2_production_arm_authorized(repo_root=repo) is False


def test_wrong_v1_tcb_hash_does_not_authorize(tmp_path):
    repo = _v2_commit_freeze_tree(tmp_path)
    payload = _v2_valid_arm_payload(repo)
    _v2_commit_arm(repo, payload)
    assert v2p.v2_production_arm_authorized(repo_root=repo) is True
    # Mutate a TCB file after the fact (worktree + a further commit): the
    # authorization must now fail because the ARM commit's own TCB no longer
    # matches the frozen hashes -- so simulate by re-checking a state where
    # the tracked LIB bytes at the ARM commit itself were wrong from the
    # start.
    repo2 = _v2_commit_freeze_tree(tmp_path / "repo2")
    lib_path = repo2 / prod.LIB_REL
    _write(lib_path, lib_path.read_bytes() + b"\n# tampered\n")
    _git(repo2, "add", "-A")
    _git(repo2, "commit", "-m", "tamper v1 lib before arm")
    payload2 = _v2_valid_arm_payload(repo2)
    _v2_commit_arm(repo2, payload2)
    assert v2p.v2_production_arm_authorized(repo_root=repo2) is False


def test_old_v1_arm_does_not_authorize_v2(tmp_path):
    repo = _v2_commit_freeze_tree(tmp_path)
    # Only a V1-style ARM file exists (different path); no V2 ARM at all.
    v1_style_payload = {"production_monte_carlo_arm_authorized": True}
    _write(repo / prod.CANONICAL_ARM_PATH, json.dumps(v1_style_payload, indent=2) + "\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "v1-style arm only")
    assert v2p.v2_production_arm_authorized(repo_root=repo) is False


def test_consumed_authority_does_not_authorize(tmp_path):
    repo = _v2_commit_freeze_tree(tmp_path)
    payload = _v2_valid_arm_payload(repo)
    payload["authorization_consumed"] = True
    _v2_commit_arm(repo, payload, message="already consumed")
    assert v2p.v2_production_arm_authorized(repo_root=repo) is False


@pytest.mark.parametrize(
    "path_attr",
    [
        "CANONICAL_V2_RESULT_PATH",
        "CANONICAL_V2_WORLD_RECORDS_PATH",
        "CANONICAL_V2_RESERVATION_PATH",
        "CANONICAL_V2_CLAIM_PATH",
    ],
)
def test_conflicting_protected_artifact_fails_closed(tmp_path, path_attr):
    repo = _v2_commit_freeze_tree(tmp_path)
    payload = _v2_valid_arm_payload(repo)
    _v2_commit_arm(repo, payload)
    assert v2p.v2_production_arm_authorized(repo_root=repo) is True
    rel = getattr(v2p, path_attr)
    _write(repo / rel, "{}\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", f"conflicting {path_attr}")
    assert v2p.v2_production_arm_authorized(repo_root=repo) is False


def test_worktree_only_mutation_does_not_authorize(tmp_path):
    repo = _v2_commit_freeze_tree(tmp_path)
    payload = _v2_valid_arm_payload(repo)
    _v2_commit_arm(repo, payload)
    assert v2p.v2_production_arm_authorized(repo_root=repo) is True
    # Mutate the ARM file in the worktree without committing.
    arm_path = repo / v2p.CANONICAL_V2_ARM_PATH
    live = json.loads(arm_path.read_text(encoding="utf-8"))
    live["authorization_consumed"] = True
    _write(arm_path, json.dumps(live, indent=2, sort_keys=True) + "\n")
    # Authorization is evaluated from committed git object bytes (HEAD), so
    # the worktree-only mutation must not change the answer.
    assert v2p.v2_production_arm_authorized(repo_root=repo) is True
    committed = json.loads(_git(repo, "cat-file", "blob", f"HEAD:{v2p.CANONICAL_V2_ARM_PATH}"))
    assert committed["authorization_consumed"] is False


# --- Part D: production driver refuses without a real ARM -------------------


def test_run_canonical_v2_production_grid_refuses_without_arm():
    assert v2p.v2_production_arm_authorized() is False
    with pytest.raises(v2p.V2ProductionNotArmed):
        v2p.run_canonical_v2_production_grid()


def test_evaluate_v2_production_world_refuses_without_arm():
    with pytest.raises(v2p.V2ProductionNotArmed):
        v2p.evaluate_v2_production_world("NULL", 5000, 0)


def test_evaluate_v2_production_world_refuses_caller_arguments():
    with pytest.raises(lib.SyntheticExecutionNotAuthorized):
        v2p.evaluate_v2_production_world("NULL", 5000, 0, root_seed=999)


def test_run_canonical_v2_production_grid_refuses_caller_arguments():
    with pytest.raises(lib.SyntheticExecutionNotAuthorized):
        v2p.run_canonical_v2_production_grid(workers=4)


def test_evaluate_v2_production_world_refuses_non_canonical_job():
    with pytest.raises(lib.SyntheticExecutionNotAuthorized):
        v2p.evaluate_v2_production_world("NULL", 123456, 0)


def test_caller_provided_world_list_cannot_authorize_a_run():
    # There is no parameter anywhere on the driver entrypoints that accepts a
    # caller-supplied world list; canonical_v2_production_jobs() is the sole
    # source of truth, takes no arguments, and run_canonical_v2_production_grid
    # only ever iterates it (proven equal to it in
    # test_canonical_v2_jobs_are_exactly_v1_frozen_planned_jobs). Any extra
    # positional/keyword argument -- including an attempted world list -- is
    # refused outright (test_run_canonical_v2_production_grid_refuses_caller_arguments).
    import inspect

    assert dict(inspect.signature(v2p.canonical_v2_production_jobs).parameters) == {}
    params = inspect.signature(v2p.run_canonical_v2_production_grid).parameters
    assert set(params) == {"args", "kwargs"}


def test_caller_provided_result_cannot_become_authority(tmp_path):
    fabricated = tuple(
        v2.WorldRecordV2(
            world_id="fake",
            scenario="NULL",
            N=5000,
            world_index=0,
            world_state=v2.WORLD_VALID,
            L=10,
            selection_state=v2.SELECTION_SELECTED,
            selected_candidate=None,
            taxonomy="NO_DISCOVERY",
        )
        for _ in range(3200)
    )
    with pytest.raises(v2p.V2ProductionNotArmed):
        v2p.mint_v2_result(fabricated)


# --- Part E: production safety invariants at this HEAD -----------------------


def test_no_real_v2_arm_exists_in_project_history():
    assert v2p.v2_production_arm_authorized() is False
    assert not (REPO / v2p.CANONICAL_V2_ARM_PATH).exists()


def test_v2_production_identity_reports_unarmed_and_unconsumed():
    identity = v2p.v2_production_identity()
    assert identity["v2_production_arm_authorized"] is False
    assert identity["production_calibration_executed"] is False
    assert identity["production_result_minted"] is False
    assert identity["world_records_created"] is False
    assert identity["execution_reserved"] is False
    assert identity["execution_claimed"] is False
    assert identity["authorization_consumed"] is False
    assert identity["v1_attempt_status"] == "INCOMPLETE_EXECUTION_NO_METHODOLOGY_CLAIM"
    assert identity["v1_3087_subset_claimable"] is False


def test_v1_tcb_intact_at_this_head():
    v2p.assert_v1_tcb_intact()


def test_production_module_never_writes_any_file():
    # This module contains zero file-write calls: it cannot modify the frozen
    # fixture, the freeze artifact, or mint any authority artifact.
    import inspect

    source = inspect.getsource(v2p)
    assert "write_text" not in source
    assert "write_bytes" not in source
    assert ".write(" not in source
