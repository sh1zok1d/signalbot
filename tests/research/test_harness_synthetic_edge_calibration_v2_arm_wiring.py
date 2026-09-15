"""Adversarial ARM authorization wiring tests for the 33/33 freeze trust boundary.

Disposable clones only. These tests must not create a real ARM in project
history, consume a real reservation, run the canonical 3200-world grid, or
mint RESULT/WORLD_RECORDS.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from scripts.research import harness_synthetic_edge_calibration_v2_production as v2p
from tests.research.test_harness_synthetic_edge_calibration_v2_production import (
    _git,
    _patch_loaded_runtime_to_commit,
    _v2_commit_arm,
    _v2_commit_freeze_tree,
    _v2_valid_arm_payload,
    _write,
)

REPO = Path(__file__).resolve().parents[2]
OLD_RANK_POLICY_FREEZE_SHA256 = (
    "64a5dfb99411940658a69ce7b6b0339851158c2a987ad12b94bb1fbf96fce2ad"
)


def test_a_old_rank_policy_freeze_arm_alone_refused(tmp_path):
    repo = _v2_commit_freeze_tree(tmp_path)
    payload = _v2_valid_arm_payload(repo)
    payload["freeze_artifact_path"] = v2p.V2_POLICY_FREEZE_ARTIFACT_REL
    payload["freeze_artifact_sha256"] = OLD_RANK_POLICY_FREEZE_SHA256
    _v2_commit_arm(repo, payload, message="old rank-policy freeze arm")
    assert v2p.v2_production_arm_authorized(repo_root=repo) is False


def test_a_arm_child_of_rank_policy_freeze_refused(tmp_path):
    repo = _v2_commit_freeze_tree(tmp_path)
    _git(repo, "checkout", "-q", v2p.FROZEN_V2_POLICY_FREEZE_HEAD)
    payload = _v2_valid_arm_payload(repo)
    _v2_commit_arm(repo, payload, message="arm on rank-policy freeze")
    assert v2p.v2_production_arm_authorized(repo_root=repo) is False


def test_b_correct_33_33_binding_authorizes_historical_layer(tmp_path):
    repo = _v2_commit_freeze_tree(tmp_path)
    payload = _v2_valid_arm_payload(repo)
    arm_commit = _v2_commit_arm(repo, payload)
    assert v2p.v2_production_arm_authorized(repo_root=repo) is True
    bound = v2p.verify_historical_v2_execution_authority(repo, arm_commit)
    assert bound["freeze_parent_head"] == v2p.FROZEN_V2_33_33_FREEZE_HEAD
    assert bound["freeze_parent_tree"] == v2p.FROZEN_V2_33_33_FREEZE_TREE
    assert bound["canonical_v2_plan_sha256"] == v2p.FROZEN_CANONICAL_V2_PLAN_SHA256


@pytest.mark.parametrize(
    "field,value",
    [
        ("freeze_parent_head", "0" * 40),
        ("freeze_parent_tree", "0" * 40),
        ("freeze_artifact_sha256", "0" * 64),
        ("reviewed_implementation_head", "0" * 40),
        ("reviewed_implementation_tree", "0" * 40),
        ("canonical_v2_plan_sha256", "0" * 64),
        ("canonical_world_count", 3199),
    ],
)
def test_c_to_k_wrong_required_binding_refused(tmp_path, field, value):
    repo = _v2_commit_freeze_tree(tmp_path)
    payload = _v2_valid_arm_payload(repo)
    payload[field] = value
    _v2_commit_arm(repo, payload, message=f"wrong {field}")
    assert v2p.v2_production_arm_authorized(repo_root=repo) is False


def test_h_mutated_inherited_ladder_at_arm_commit_refused(tmp_path):
    repo = _v2_commit_freeze_tree(tmp_path)
    ladder = repo / v2p.V2_INHERITED_LADDER_REL
    _write(ladder, ladder.read_bytes() + b"\n# mutated inherited ladder\n")
    payload = _v2_valid_arm_payload(repo)
    _v2_commit_arm(repo, payload, message="arm with mutated inherited ladder")
    assert v2p.v2_production_arm_authorized(repo_root=repo) is False


def test_i_mutated_production_at_arm_commit_refused(tmp_path):
    repo = _v2_commit_freeze_tree(tmp_path)
    production = repo / v2p.V2_PRODUCTION_REL
    _write(production, production.read_bytes() + b"\n# mutated production\n")
    payload = _v2_valid_arm_payload(repo)
    _v2_commit_arm(repo, payload, message="arm with mutated production")
    assert v2p.v2_production_arm_authorized(repo_root=repo) is False


def test_l_a002_marked_governing_refused(tmp_path):
    repo = _v2_commit_freeze_tree(tmp_path)
    payload = _v2_valid_arm_payload(repo)
    payload["amendment_002_status"] = "GOVERNING_AUTHORITY"
    payload["amendment_002_governs_executable_science"] = True
    _v2_commit_arm(repo, payload, message="a002 governing claim")
    assert v2p.v2_production_arm_authorized(repo_root=repo) is False


def test_l_a002_boolean_zero_is_not_false(tmp_path):
    repo = _v2_commit_freeze_tree(tmp_path)
    payload = _v2_valid_arm_payload(repo)
    payload["amendment_002_governs_executable_science"] = 0
    _v2_commit_arm(repo, payload, message="a002 zero not false")
    assert v2p.v2_production_arm_authorized(repo_root=repo) is False


def test_m_alternate_caller_freeze_refused(tmp_path):
    repo = _v2_commit_freeze_tree(tmp_path)
    freeze_path = repo / v2p.V2_FREEZE_ARTIFACT_REL
    attacker = json.loads(freeze_path.read_text(encoding="utf-8"))
    attacker["reviewed_implementation"]["head"] = "0" * 40
    attacker["reviewed_implementation"]["tree"] = "1" * 40
    _write(freeze_path, json.dumps(attacker, indent=2, sort_keys=True) + "\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "attacker replacement freeze")
    payload = dict(v2p.V2_ARM_REQUIRED_LITERALS)
    payload.update(
        {
            "freeze_parent_head": _git(repo, "rev-parse", "HEAD"),
            "freeze_parent_tree": _git(repo, "rev-parse", "HEAD^{tree}"),
            "freeze_artifact_path": v2p.V2_FREEZE_ARTIFACT_REL,
            "freeze_artifact_sha256": hashlib.sha256(freeze_path.read_bytes()).hexdigest(),
            "freeze_artifact_size": freeze_path.stat().st_size,
            "reviewed_implementation_head": "0" * 40,
            "reviewed_implementation_tree": "1" * 40,
            "v2_policy_sha256": "2" * 64,
            "v2_policy_size": 1,
            "canonical_v2_plan_sha256": "3" * 64,
            "canonical_world_count": 3200,
            "original_prereg_head": v2p.FROZEN_ORIGINAL_PREREG_HEAD,
            "original_prereg_tree": v2p.FROZEN_ORIGINAL_PREREG_TREE,
            "amendment_001_head": v2p.FROZEN_AMENDMENT_001_HEAD,
            "amendment_001_tree": v2p.FROZEN_AMENDMENT_001_TREE,
            "amendment_003_md_sha256": "4" * 64,
            "amendment_003_json_sha256": "5" * 64,
            "amendment_004_md_sha256": "6" * 64,
            "amendment_004_json_sha256": "7" * 64,
        }
    )
    _v2_commit_arm(repo, payload, message="arm on attacker freeze")
    assert v2p.v2_production_arm_authorized(repo_root=repo) is False


def test_n_working_tree_substitution_cannot_redefine_historical_authority(tmp_path):
    repo = _v2_commit_freeze_tree(tmp_path)
    payload = _v2_valid_arm_payload(repo)
    arm_commit = _v2_commit_arm(repo, payload)
    bound = v2p.verify_historical_v2_execution_authority(repo, arm_commit)
    freeze_path = repo / v2p.V2_FREEZE_ARTIFACT_REL
    _write(freeze_path, b'{"attacker": true}\n')
    ladder = repo / v2p.V2_INHERITED_LADDER_REL
    _write(ladder, ladder.read_bytes() + b"\n# worktree only\n")
    bound2 = v2p.verify_historical_v2_execution_authority(repo, arm_commit)
    assert bound2 == bound
    assert v2p.v2_production_arm_authorized(repo_root=repo) is True


def test_n_worktree_only_arm_is_refused(tmp_path):
    repo = _v2_commit_freeze_tree(tmp_path)
    payload = _v2_valid_arm_payload(repo)
    _write(
        repo / v2p.CANONICAL_V2_ARM_PATH,
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
    )
    assert v2p.v2_production_arm_authorized(repo_root=repo) is False


def test_o_branch_movement_does_not_change_historical_authorization(tmp_path):
    repo = _v2_commit_freeze_tree(tmp_path)
    payload = _v2_valid_arm_payload(repo)
    arm_commit = _v2_commit_arm(repo, payload)
    bound = v2p.verify_historical_v2_execution_authority(repo, arm_commit)
    _git(repo, "checkout", "-q", "-b", "moved-branch")
    _write(repo / "docs/NOTE.md", "branch moved\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "unrelated branch movement")
    bound_moved = v2p.verify_historical_v2_execution_authority(repo, arm_commit)
    assert bound_moved == bound
    assert v2p.v2_production_arm_authorized(repo_root=repo) is False


def test_p_second_reservation_refused(tmp_path):
    repo = _v2_commit_freeze_tree(tmp_path)
    payload = _v2_valid_arm_payload(repo)
    arm_commit = _v2_commit_arm(repo, payload)
    v2p.establish_v2_durable_reservation(repo, arm_commit)
    with pytest.raises(v2p.SyntheticExecutionNotAuthorized):
        v2p.establish_v2_durable_reservation(repo, arm_commit)


def test_q_reuse_after_consumption_refused(tmp_path, monkeypatch):
    repo = _v2_commit_freeze_tree(tmp_path)
    payload = _v2_valid_arm_payload(repo)
    arm_commit = _v2_commit_arm(repo, payload)
    _patch_loaded_runtime_to_commit(monkeypatch, repo, arm_commit)
    v2p.establish_v2_durable_reservation(repo, arm_commit)
    reservation_path = repo / v2p.CANONICAL_V2_RESERVATION_PATH
    reservation = json.loads(reservation_path.read_text(encoding="utf-8"))
    reservation["authorization_consumed"] = True
    _write(reservation_path, json.dumps(reservation, indent=2, sort_keys=True) + "\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "consume reservation")
    with pytest.raises(v2p.SyntheticExecutionNotAuthorized):
        v2p.open_v2_production_session(repo_root=repo, arm_commit=arm_commit)


def test_self_attested_authority_chain_refused(tmp_path):
    """Internally consistent attacker freeze+impl+ARM still lacks the reviewed anchor."""
    repo = tmp_path / "attacker"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.email", "attacker@example.com")
    _git(repo, "config", "user.name", "attacker")
    _git(repo, "config", "commit.gpgsign", "false")
    impl = b"print('attacker implementation')\n"
    freeze = {
        "reviewed_implementation": {"head": "a" * 40, "tree": "b" * 40},
        "methodology_authority": {
            "amendment_002": {
                "status": "REJECTED_HISTORICAL_AUTHORITY",
                "governs_executable_science": False,
            }
        },
        "execution_authoritative_implementation_sources": [
            {
                "path": v2p.V2_INHERITED_LADDER_REL,
                "git_blob": "c" * 40,
                "sha256": hashlib.sha256(impl).hexdigest(),
                "size_bytes": len(impl),
            },
            {
                "path": v2p.V2_PRODUCTION_REL,
                "git_blob": "d" * 40,
                "sha256": hashlib.sha256(impl).hexdigest(),
                "size_bytes": len(impl),
            },
        ],
    }
    _write(repo / v2p.V2_INHERITED_LADDER_REL, impl)
    _write(repo / v2p.V2_PRODUCTION_REL, impl)
    _write(repo / v2p.V2_FREEZE_ARTIFACT_REL, json.dumps(freeze, indent=2) + "\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "attacker freeze")
    freeze_head = _git(repo, "rev-parse", "HEAD")
    freeze_tree = _git(repo, "rev-parse", "HEAD^{tree}")
    freeze_bytes = (repo / v2p.V2_FREEZE_ARTIFACT_REL).read_bytes()
    payload = dict(v2p.V2_ARM_REQUIRED_LITERALS)
    payload.update(
        {
            "freeze_parent_head": freeze_head,
            "freeze_parent_tree": freeze_tree,
            "freeze_artifact_path": v2p.V2_FREEZE_ARTIFACT_REL,
            "freeze_artifact_sha256": hashlib.sha256(freeze_bytes).hexdigest(),
            "freeze_artifact_size": len(freeze_bytes),
            "reviewed_implementation_head": freeze_head,
            "reviewed_implementation_tree": freeze_tree,
            "v2_policy_sha256": hashlib.sha256(impl).hexdigest(),
            "v2_policy_size": len(impl),
            "canonical_v2_plan_sha256": v2p.FROZEN_CANONICAL_V2_PLAN_SHA256,
            "canonical_world_count": 3200,
            "original_prereg_head": v2p.FROZEN_ORIGINAL_PREREG_HEAD,
            "original_prereg_tree": v2p.FROZEN_ORIGINAL_PREREG_TREE,
            "amendment_001_head": v2p.FROZEN_AMENDMENT_001_HEAD,
            "amendment_001_tree": v2p.FROZEN_AMENDMENT_001_TREE,
            "amendment_003_md_sha256": "e" * 64,
            "amendment_003_json_sha256": "f" * 64,
            "amendment_004_md_sha256": "1" * 64,
            "amendment_004_json_sha256": "2" * 64,
        }
    )
    _v2_commit_arm(repo, payload, message="self-attested arm")
    assert v2p.v2_production_arm_authorized(repo_root=repo) is False
    with pytest.raises(v2p.SyntheticExecutionNotAuthorized):
        v2p.verify_historical_v2_execution_authority(repo, _git(repo, "rev-parse", "HEAD"))


def test_historical_authority_uses_git_objects_not_current_checkout_bytes(tmp_path):
    repo = _v2_commit_freeze_tree(tmp_path)
    payload = _v2_valid_arm_payload(repo)
    arm_commit = _v2_commit_arm(repo, payload)
    production = repo / v2p.V2_PRODUCTION_REL
    _write(production, production.read_bytes() + b"\n# current checkout substitution\n")
    assert v2p.verify_historical_v2_execution_authority(repo, arm_commit)["arm_commit"] == arm_commit
    assert v2p.v2_production_arm_authorized(repo_root=repo) is True


def test_live_executed_runtime_refuses_33_33_freeze_bytes_after_wiring_repair():
    with pytest.raises(v2p.SyntheticExecutionNotAuthorized, match="loaded runtime bytes"):
        v2p._assert_executed_runtime_bound_to_commit(
            REPO, v2p.FROZEN_V2_33_33_FREEZE_HEAD
        )


def test_executed_runtime_check_refuses_disposable_clone_root_mismatch(tmp_path):
    repo = _v2_commit_freeze_tree(tmp_path)
    payload = _v2_valid_arm_payload(repo)
    arm_commit = _v2_commit_arm(repo, payload)
    with pytest.raises(v2p.SyntheticExecutionNotAuthorized, match="loaded runtime bytes"):
        v2p._assert_executed_runtime_bound_to_commit(repo, arm_commit)


def test_live_runtime_bytes_match_current_head():
    live = Path(v2p.__file__).read_bytes()
    head = v2p._commit_blob(REPO, "HEAD", v2p.V2_PRODUCTION_REL)
    if live != head:
        pytest.skip("worktree production.py differs from HEAD before the repair commit")
    v2p._assert_executed_runtime_bound_to_commit(REPO, "HEAD")


def test_33_33_freeze_is_required_and_rank_policy_constants_are_not_aliases():
    assert v2p.V2_FREEZE_ARTIFACT_REL != v2p.V2_POLICY_FREEZE_ARTIFACT_REL
    assert v2p.FROZEN_V2_33_33_FREEZE_ARTIFACT_SHA256 != OLD_RANK_POLICY_FREEZE_SHA256
    assert v2p.FROZEN_REVIEWED_IMPLEMENTATION_HEAD == v2p.FROZEN_V2_33_33_IMPLEMENTATION_HEAD
    assert v2p.FROZEN_V2_POLICY_REVIEWED_IMPLEMENTATION_HEAD != v2p.FROZEN_V2_33_33_IMPLEMENTATION_HEAD
    assert v2p.FROZEN_CANONICAL_WORLD_COUNT == 3200
