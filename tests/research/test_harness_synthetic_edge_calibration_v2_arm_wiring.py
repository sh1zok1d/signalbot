"""Adversarial ARM authorization wiring tests for the V2 execution-freeze
trust boundary.

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
# Historical, pre-self-reference-repair freeze commit. Its own recorded
# production.py bytes necessarily predate this repair's changes to that same
# file, so it is used below only as a fixed, known-divergent-bytes fixture --
# never as production authority (nothing in production.py references it).
HISTORICAL_POST_WIRING_FREEZE_HEAD = "75f12bd31eac631a3baedd4a627344c0f2d40190"


def test_a_old_rank_policy_freeze_arm_alone_refused(tmp_path):
    repo = _v2_commit_freeze_tree(tmp_path)
    payload = _v2_valid_arm_payload(repo)
    payload["freeze_artifact_path"] = v2p.V2_POLICY_FREEZE_ARTIFACT_REL
    payload["freeze_artifact_sha256"] = OLD_RANK_POLICY_FREEZE_SHA256
    _v2_commit_arm(repo, payload, message="old rank-policy freeze arm")
    assert v2p.v2_production_arm_authorized(repo_root=repo) is False


def test_a_arm_child_of_rank_policy_freeze_refused(tmp_path):
    repo = _v2_commit_freeze_tree(tmp_path)
    valid_freeze_commit = _git(repo, "rev-parse", "HEAD")
    payload = _v2_valid_arm_payload(repo, freeze_commit=valid_freeze_commit)
    _git(repo, "checkout", "-q", v2p.FROZEN_V2_POLICY_FREEZE_HEAD)
    _v2_commit_arm(repo, payload, message="arm on rank-policy freeze")
    assert v2p.v2_production_arm_authorized(repo_root=repo) is False


def test_b_correct_binding_authorizes_historical_layer(tmp_path):
    repo = _v2_commit_freeze_tree(tmp_path)
    freeze_commit = _git(repo, "rev-parse", "HEAD")
    freeze_tree = _git(repo, "rev-parse", "HEAD^{tree}")
    payload = _v2_valid_arm_payload(repo)
    arm_commit = _v2_commit_arm(repo, payload)
    assert v2p.v2_production_arm_authorized(repo_root=repo) is True
    bound = v2p.verify_historical_v2_execution_authority(repo, arm_commit)
    assert bound["freeze_parent_head"] == freeze_commit
    assert bound["freeze_parent_tree"] == freeze_tree
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


def _build_disposable_freeze_commit(tmp_path: Path, *, name: str, mutate=None) -> tuple[Path, str]:
    """A disposable clone with a freshly-built freeze committed as an
    immediate child of the live implementation HEAD, optionally mutated (via
    ``mutate(freeze_doc) -> freeze_doc``) before it is committed. Returns
    ``(repo, freeze_commit)``."""
    import subprocess

    from tests.research.test_harness_synthetic_edge_calibration_v2_production import (
        _v2_execution_freeze_artifact,
    )

    repo = tmp_path / name
    subprocess.run(
        ["git", "clone", "--local", "--", str(REPO), str(repo)],
        check=True,
        capture_output=True,
        text=True,
    )
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "test")
    _git(repo, "config", "commit.gpgsign", "false")
    implementation_head = _git(repo, "rev-parse", "HEAD")
    implementation_tree = _git(repo, "rev-parse", "HEAD^{tree}")
    freeze_doc = _v2_execution_freeze_artifact(repo, implementation_head, implementation_tree)
    if mutate is not None:
        freeze_doc = mutate(freeze_doc)
    freeze_path = repo / v2p.CANONICAL_V2_EXECUTION_FREEZE_PATH
    _write(freeze_path, json.dumps(freeze_doc, indent=2, sort_keys=True) + "\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "v2 execution freeze")
    return repo, _git(repo, "rev-parse", "HEAD")


def test_l_freeze_document_a002_governing_refused(tmp_path):
    """Even if an ARM payload's own A002 literals are correct, a freeze
    document that itself claims A002 governs must not authenticate."""

    def mutate(freeze):
        freeze["methodology_authority"]["amendment_002"]["governs_executable_science"] = True
        return freeze

    repo, freeze_commit = _build_disposable_freeze_commit(tmp_path, name="repo", mutate=mutate)
    assert v2p._authenticate_v2_execution_freeze(repo, freeze_commit) is None


def test_l_freeze_document_a003_non_governing_refused(tmp_path):
    """A freeze that tries to demote Amendment_003 to non-governing (a role
    swap toward A002's role) must not authenticate."""

    def mutate(freeze):
        freeze["methodology_authority"]["amendment_003"]["governs_executable_science"] = False
        return freeze

    repo, freeze_commit = _build_disposable_freeze_commit(tmp_path, name="repo", mutate=mutate)
    assert v2p._authenticate_v2_execution_freeze(repo, freeze_commit) is None


def test_m_alternate_caller_freeze_refused(tmp_path):
    repo = _v2_commit_freeze_tree(tmp_path)
    freeze_path = repo / v2p.CANONICAL_V2_EXECUTION_FREEZE_PATH
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
            "freeze_artifact_path": v2p.CANONICAL_V2_EXECUTION_FREEZE_PATH,
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
    freeze_path = repo / v2p.CANONICAL_V2_EXECUTION_FREEZE_PATH
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
    """Internally consistent attacker freeze+impl+ARM still lacks the
    structural parent topology a real freeze/implementation would have."""
    repo = tmp_path / "attacker"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.email", "attacker@example.com")
    _git(repo, "config", "user.name", "attacker")
    _git(repo, "config", "commit.gpgsign", "false")
    impl = b"print('attacker implementation')\n"
    freeze = {
        "schema": v2p.V2_EXECUTION_FREEZE_SCHEMA,
        "reviewed_implementation": {"head": "a" * 40, "tree": "b" * 40},
        "methodology_authority": {
            "amendment_002": {
                "status": "REJECTED_HISTORICAL_AUTHORITY",
                "governs_executable_science": False,
            },
            "amendment_003": {"governs_executable_science": True},
            "amendment_004": {"governs_executable_science": True, "amends": "AMENDMENT_003"},
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
    _write(repo / v2p.CANONICAL_V2_EXECUTION_FREEZE_PATH, json.dumps(freeze, indent=2) + "\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "attacker freeze")
    freeze_head = _git(repo, "rev-parse", "HEAD")
    freeze_tree = _git(repo, "rev-parse", "HEAD^{tree}")
    freeze_bytes = (repo / v2p.CANONICAL_V2_EXECUTION_FREEZE_PATH).read_bytes()
    payload = dict(v2p.V2_ARM_REQUIRED_LITERALS)
    payload.update(
        {
            "freeze_parent_head": freeze_head,
            "freeze_parent_tree": freeze_tree,
            "freeze_artifact_path": v2p.CANONICAL_V2_EXECUTION_FREEZE_PATH,
            "freeze_artifact_sha256": hashlib.sha256(freeze_bytes).hexdigest(),
            "freeze_artifact_size": len(freeze_bytes),
            "reviewed_implementation_head": "a" * 40,
            "reviewed_implementation_tree": "b" * 40,
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
    # The freeze here is itself a root commit (zero parents): it cannot
    # structurally point at any implementation commit at all, so this fails
    # closed before any content field is even inspected.
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


def test_live_executed_runtime_refuses_stale_historical_freeze_bytes():
    """The live runtime's production.py today differs from the recorded
    bytes of a historical, pre-self-reference-repair freeze commit -- this
    proves the live-byte check genuinely compares content, not merely
    presence. Nothing in production.py references this historical SHA."""
    with pytest.raises(v2p.SyntheticExecutionNotAuthorized, match="loaded runtime bytes"):
        v2p._assert_executed_runtime_bound_to_commit(REPO, HISTORICAL_POST_WIRING_FREEZE_HEAD)


def test_executed_runtime_check_refuses_disposable_clone_root_mismatch(tmp_path):
    import subprocess as sp

    repo = tmp_path / "clone"
    sp.run(
        ["git", "clone", "--local", "--", str(REPO), str(repo)],
        check=True,
        capture_output=True,
    )
    historical = HISTORICAL_POST_WIRING_FREEZE_HEAD
    with pytest.raises(v2p.SyntheticExecutionNotAuthorized, match="loaded runtime bytes"):
        v2p._assert_executed_runtime_bound_to_commit(repo, historical)


def test_live_runtime_bytes_match_current_head():
    live = Path(v2p.__file__).read_bytes()
    head = v2p._commit_blob(REPO, "HEAD", v2p.V2_PRODUCTION_REL)
    if live != head:
        pytest.skip("worktree production.py differs from HEAD before the repair commit")
    v2p._assert_executed_runtime_bound_to_commit(REPO, "HEAD")


def test_execution_freeze_path_is_required_and_rank_policy_constants_are_not_aliases(tmp_path):
    assert v2p.CANONICAL_V2_EXECUTION_FREEZE_PATH != v2p.V2_POLICY_FREEZE_ARTIFACT_REL
    repo = _v2_commit_freeze_tree(tmp_path)
    implementation_head = _git(repo, "rev-parse", "HEAD^")
    assert v2p.FROZEN_V2_POLICY_REVIEWED_IMPLEMENTATION_HEAD != implementation_head
    assert v2p.FROZEN_CANONICAL_WORLD_COUNT == 3200


def test_no_freeze_identity_constants_exist_in_production_module():
    """Regression guard for the architectural bug this unit repairs: this
    module must never again hardcode a specific freeze/implementation SHA
    as execution authority."""
    forbidden = (
        "FROZEN_V2_33_33_FREEZE_HEAD",
        "FROZEN_V2_33_33_FREEZE_TREE",
        "FROZEN_V2_33_33_FREEZE_ARTIFACT_SHA256",
        "FROZEN_V2_33_33_FREEZE_ARTIFACT_SIZE",
        "FROZEN_V2_33_33_IMPLEMENTATION_HEAD",
        "FROZEN_V2_33_33_IMPLEMENTATION_TREE",
        "FROZEN_REVIEWED_IMPLEMENTATION_HEAD",
        "FROZEN_REVIEWED_IMPLEMENTATION_TREE",
    )
    for name in forbidden:
        assert not hasattr(v2p, name), f"{name} must not exist: it re-introduces the self-reference bug"
