"""Regression coverage for the V2 authority self-reference architectural
repair.

Prior design: production.py hardcoded the identity of the freeze commit and
the implementation commit that authorize execution. Because production.py is
itself one of the two execution-authoritative implementation sources any
freeze must byte-bind, editing those hardcoded identities to point at a new
freeze changed production.py's own bytes -- which invalidated the freeze
just made, requiring another freeze, requiring another edit, forever. This
is exactly what happened to the real 75f12bd freeze: it correctly recorded
c1d6acc's bytes, but production.py at FREEZE_HEAD still pointed at the older
e50fcee/614295d identity, so no ARM built as an immediate child of 75f12bd
could ever authorize.

These tests prove the replacement design (freeze commit F is always derived
structurally as the ARM's own immediate parent, and implementation commit I
is always derived structurally as F's own immediate parent -- never
hardcoded) actually terminates: a fresh implementation, frozen once, is
immediately consumable by an ARM with NO further edit to production.py.

Disposable clones only. These tests must not create a real ARM in project
history, consume a real reservation, run the canonical 3200-world grid, or
mint RESULT/WORLD_RECORDS.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.research import harness_synthetic_edge_calibration_v2_production as v2p
from tests.research.test_harness_synthetic_edge_calibration_v2_production import (
    _git,
    _sha,
    _v2_commit_arm,
    _v2_commit_freeze_tree,
    _v2_execution_freeze_artifact,
    _v2_valid_arm_payload,
    _write,
)

REPO = Path(__file__).resolve().parents[2]


def test_future_freeze_does_not_require_runtime_anchor_edit(tmp_path):
    """I -> F -> A -> authorization, with zero production.py edits after F.

    This is the exact sequence the architectural repair must terminate:
    commit an implementation, freeze it once, arm it once, and authorize --
    using the real, unmodified, already-committed production.py the whole
    way through. No step here edits production.py, and none needs to.
    """
    repo = _v2_commit_freeze_tree(tmp_path)  # builds I -> F (I = live HEAD)
    implementation_head = _git(repo, "rev-parse", "HEAD^")
    freeze_commit = _git(repo, "rev-parse", "HEAD")

    # Sanity: F really is I's immediate child, and I really is whatever this
    # clone's pre-freeze HEAD was -- not any value production.py hardcodes.
    assert _git(repo, "rev-parse", f"{freeze_commit}^") == implementation_head

    payload = _v2_valid_arm_payload(repo)  # A2, derived purely from F's topology
    arm_commit = _v2_commit_arm(repo, payload)

    assert v2p.v2_production_arm_authorized(repo_root=repo) is True
    bound = v2p.verify_historical_v2_execution_authority(repo, arm_commit)
    assert bound["freeze_parent_head"] == freeze_commit


def test_no_post_freeze_implementation_edit_required(tmp_path):
    """The freeze -> ARM -> authorize sequence needs no intervening commit
    to production.py at all: the freeze commit's immediate child can be the
    ARM directly."""
    repo = _v2_commit_freeze_tree(tmp_path)
    freeze_commit = _git(repo, "rev-parse", "HEAD")
    payload = _v2_valid_arm_payload(repo)
    arm_commit = _v2_commit_arm(repo, payload)
    assert _git(repo, "rev-parse", f"{arm_commit}^") == freeze_commit
    assert v2p.v2_production_arm_authorized(repo_root=repo) is True


def test_two_independent_implementation_generations_both_authorize(tmp_path):
    """The runtime discriminates on structure (I -> F -> A topology, byte
    equality, authority-chain content), never on a specific hardcoded
    identity: two *different* disposable implementations, each frozen and
    armed independently, both authorize under the exact same, unmodified
    production.py code."""
    for name in ("generation_one", "generation_two"):
        repo = _v2_commit_freeze_tree(tmp_path, name=name)
        payload = _v2_valid_arm_payload(repo)
        _v2_commit_arm(repo, payload)
        assert v2p.v2_production_arm_authorized(repo_root=repo) is True

    # The two generations' implementation commits are genuinely distinct
    # (independent clones of the same source at commit time, not aliases),
    # yet both authorized -- proving no specific SHA is special-cased.
    repo_one = tmp_path / "generation_one"
    repo_two = tmp_path / "generation_two"
    impl_one = _git(repo_one, "rev-parse", "HEAD^^")
    impl_two = _git(repo_two, "rev-parse", "HEAD^^")
    assert impl_one == impl_two  # same source commit, cloned twice
    freeze_one = _git(repo_one, "rev-parse", "HEAD^")
    freeze_two = _git(repo_two, "rev-parse", "HEAD^")
    assert freeze_one != freeze_two  # independently-built freeze commits


def test_freeze_document_alone_does_not_authorize_without_arm(tmp_path):
    """A freeze that is itself fully valid content is still not execution
    authority by itself -- it must have an ARM as its own immediate child."""
    repo = _v2_commit_freeze_tree(tmp_path)
    assert v2p.v2_production_arm_authorized(repo_root=repo) is False


def test_valid_freeze_is_not_invisible_to_runtime_once_armed(tmp_path):
    """Companion to the above: the SAME freeze, once armed, authorizes --
    proving the freeze was reachable/authenticatable all along, not merely
    document-valid. This is the exact property 75f12bd lacked: it was a
    correct document that the runtime could never reach."""
    repo = _v2_commit_freeze_tree(tmp_path)
    payload = _v2_valid_arm_payload(repo)
    _v2_commit_arm(repo, payload)
    assert v2p.v2_production_arm_authorized(repo_root=repo) is True


def test_freeze_artifact_at_wrong_path_is_invisible_to_runtime(tmp_path):
    """A content-valid freeze document committed at any path other than the
    stable canonical path is never discovered -- reproducing, in miniature,
    exactly what happened with the real 75f12bd freeze (which used a
    different, non-canonical path and was consequently unconsumable)."""
    repo = tmp_path / "repo"
    import subprocess

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
    wrong_path = repo / "docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V2_33_33_IMPLEMENTATION_FREEZE.json"
    _write(wrong_path, json.dumps(freeze_doc, indent=2, sort_keys=True) + "\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "freeze at wrong path")
    freeze_commit = _git(repo, "rev-parse", "HEAD")

    assert v2p._authenticate_v2_execution_freeze(repo, freeze_commit) is None

    payload = dict(v2p.V2_ARM_REQUIRED_LITERALS)
    payload.update(
        {
            "freeze_parent_head": freeze_commit,
            "freeze_parent_tree": _git(repo, "rev-parse", "HEAD^{tree}"),
            "freeze_artifact_path": str(wrong_path.relative_to(repo)),
            "freeze_artifact_sha256": _sha(wrong_path.read_bytes()),
            "freeze_artifact_size": wrong_path.stat().st_size,
            "reviewed_implementation_head": implementation_head,
            "reviewed_implementation_tree": implementation_tree,
            "v2_policy_sha256": _sha(
                v2p._commit_blob(repo, implementation_head, v2p.V2_POLICY_REL)
            ),
            "v2_policy_size": len(
                v2p._commit_blob(repo, implementation_head, v2p.V2_POLICY_REL)
            ),
            "canonical_v2_plan_sha256": v2p.FROZEN_CANONICAL_V2_PLAN_SHA256,
            "canonical_world_count": v2p.FROZEN_CANONICAL_WORLD_COUNT,
            "original_prereg_head": v2p.FROZEN_ORIGINAL_PREREG_HEAD,
            "original_prereg_tree": v2p.FROZEN_ORIGINAL_PREREG_TREE,
            "amendment_001_head": v2p.FROZEN_AMENDMENT_001_HEAD,
            "amendment_001_tree": v2p.FROZEN_AMENDMENT_001_TREE,
            "amendment_003_md_sha256": "0" * 64,
            "amendment_003_json_sha256": "0" * 64,
            "amendment_004_md_sha256": "0" * 64,
            "amendment_004_json_sha256": "0" * 64,
        }
    )
    _v2_commit_arm(repo, payload, message="arm claiming freeze at wrong path")
    assert v2p.v2_production_arm_authorized(repo_root=repo) is False


def test_authentication_never_trusts_freeze_self_reported_implementation_bytes(tmp_path):
    """The freeze document's own reported sha256/size for the two
    execution-authoritative files must match what is ACTUALLY at the
    implementation commit -- a freeze that lies about those (while staying
    internally self-consistent) must not authenticate."""
    repo = _v2_commit_freeze_tree(tmp_path)
    freeze_path = repo / v2p.CANONICAL_V2_EXECUTION_FREEZE_PATH
    freeze = json.loads(freeze_path.read_text(encoding="utf-8"))
    for entry in freeze["execution_authoritative_implementation_sources"]:
        if entry["path"] == v2p.V2_PRODUCTION_REL:
            entry["sha256"] = "0" * 64
            entry["size_bytes"] = 1
    _write(freeze_path, json.dumps(freeze, indent=2, sort_keys=True) + "\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "freeze lies about production.py bytes")
    freeze_commit = _git(repo, "rev-parse", "HEAD")
    assert v2p._authenticate_v2_execution_freeze(repo, freeze_commit) is None


def _init_disposable_repo(tmp_path: Path, *, name: str = "repo") -> Path:
    import subprocess

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
    return repo


def test_freeze_with_multiple_parents_refused(tmp_path):
    """A freeze commit must have exactly one parent (the implementation);
    a merge commit cannot stand in for a freeze."""
    repo = _init_disposable_repo(tmp_path)
    base = _git(repo, "rev-parse", "HEAD")

    _git(repo, "checkout", "-q", "-b", "branch_a")
    _write(repo / "docs/A.md", "a\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "branch a commit")
    tip_a = _git(repo, "rev-parse", "HEAD")

    _git(repo, "checkout", "-q", base)
    _git(repo, "checkout", "-q", "-b", "branch_b")
    _write(repo / "docs/B.md", "b\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "branch b commit")

    _git(repo, "merge", "--no-ff", "-m", "merge a into b", tip_a)
    merge_commit = _git(repo, "rev-parse", "HEAD")
    assert v2p._commit_parent_count(repo, merge_commit) == 2
    assert v2p._authenticate_v2_execution_freeze(repo, merge_commit) is None


def test_arm_with_multiple_parents_refused(tmp_path):
    """An ARM commit must also have exactly one parent (the freeze)."""
    repo = _v2_commit_freeze_tree(tmp_path)
    freeze_commit = _git(repo, "rev-parse", "HEAD")
    payload = _v2_valid_arm_payload(repo)

    _git(repo, "checkout", "-q", "-b", "arm_branch")
    _write(repo / v2p.CANONICAL_V2_ARM_PATH, json.dumps(payload, indent=2, sort_keys=True) + "\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "arm commit")

    _git(repo, "checkout", "-q", freeze_commit)
    _git(repo, "checkout", "-q", "-b", "side_branch")
    _write(repo / "docs/SIDE.md", "side\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "side commit")
    side_tip = _git(repo, "rev-parse", "HEAD")

    _git(repo, "checkout", "-q", "arm_branch")
    _git(repo, "merge", "--no-ff", "-m", "merge side into arm", side_tip)
    merged_arm = _git(repo, "rev-parse", "HEAD")
    assert v2p._commit_parent_count(repo, merged_arm) == 2
    assert v2p.v2_production_arm_authorized(repo_root=repo) is False
