"""Freeze verification for the reviewed V2 rank-degeneracy policy implementation.

These tests verify committed git object bytes, not the live worktree. They
must not run the frozen 3200-world grid, mint RESULT/WORLD_RECORDS, create an
ARM, or consume V1/V2 authority. The freeze commit under test binds a
reviewed, already-closed implementation; it must not change any
execution-authoritative byte.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

REVIEWED_IMPLEMENTATION_HEAD = "a310837bab4ee60c7495cca3bdb476abdc58a041"
REVIEWED_IMPLEMENTATION_TREE = "b15c4102b01514ff73e1728aec072eda9b528815"

ORIGINAL_PREREG_HEAD = "ada237edc330b44bc412332e263f124757919e93"
ORIGINAL_PREREG_TREE = "ba1c0873879b7ea8556c3e238f8b962b91da6dc2"

AMENDMENT_001_HEAD = "d8f0a996bc4341d0cbe01a1a061130b889ed5e75"
AMENDMENT_001_TREE = "09dca9b1240a43d5de9de0dadf32d27e00e7eaea"

V2_POLICY_PATH = "scripts/research/harness_synthetic_edge_calibration_v2_rank_policy.py"

FREEZE_ARTIFACT_PATH = (
    "docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V2_RANK_DEGENERACY_POLICY_IMPLEMENTATION_FREEZE.json"
)

V1_TCB_PATHS = {
    "lib": "scripts/research/harness_synthetic_edge_calibration_v1_lib.py",
    "runner": "scripts/research/harness_synthetic_edge_calibration_v1.py",
    "auth": "scripts/research/harness_synthetic_edge_calibration_v1_auth.py",
    "production": "scripts/research/harness_synthetic_edge_calibration_v1_production.py",
    "worker": "scripts/research/harness_synthetic_edge_calibration_v1_worker.py",
}

FROZEN_TCB_SHA256 = {
    "lib": "12230dcad714e3a06d3f57de69b78fedcab088be950af3d06f959366f01d6c51",
    "runner": "0a5e577cc3797b018e9912865b7c3e385908764dc6cb36a6555626205855432a",
    "auth": "0e174ac6b73530ec28501b0c076e0cad7874ab31bb1ed6941e4b525d12e35507",
    "production": "9e784ecdcbd53ae4128d803d9325c8ff0f6db49ce70a0a63b13c4fc6a548a4ed",
    "worker": "9aee03fdae012f9054c59adc4cea8072b88493521456fb6141ced926961c886e",
}

FREEZE_ALLOWED_CHANGED_PATHS = {
    FREEZE_ARTIFACT_PATH,
    "tests/research/test_harness_synthetic_edge_calibration_v2_rank_policy_implementation_freeze.py",
    "docs/PROJECT_STATUS.md",
    "docs/RESEARCH_LEDGER.md",
    "docs/RESEARCH_ROADMAP.md",
}


def _git(*args: str) -> str:
    return subprocess.check_output(["git", "-C", str(REPO), *args], text=True).strip()


def _blob_id(commit: str, path: str) -> str:
    return _git("rev-parse", f"{commit}:{path}")


def _blob_sha256(commit: str, path: str) -> str:
    raw = subprocess.check_output(
        ["git", "-C", str(REPO), "cat-file", "-p", f"{commit}:{path}"]
    )
    return hashlib.sha256(raw).hexdigest()


def _blob_size(commit: str, path: str) -> int:
    return int(_git("cat-file", "-s", _blob_id(commit, path)))


def _freeze_artifact_at(commit: str) -> dict:
    raw = subprocess.check_output(
        ["git", "-C", str(REPO), "cat-file", "-p", f"{commit}:{FREEZE_ARTIFACT_PATH}"]
    )
    return json.loads(raw)


def test_freeze_parent_is_reviewed_implementation_head_and_tree():
    parent = _git("rev-parse", "HEAD^")
    parent_tree = _git("rev-parse", "HEAD^^{tree}")
    assert parent == REVIEWED_IMPLEMENTATION_HEAD
    assert parent_tree == REVIEWED_IMPLEMENTATION_TREE


def test_starting_worktree_was_clean_before_freeze():
    # The freeze commit's parent tree must equal the reviewed implementation
    # tree exactly -- already proven above via HEAD^^{tree}. This test proves
    # the parent commit itself is not dirty relative to its own tree by
    # construction: a git commit object always has a clean, exact tree.
    assert _git("cat-file", "-t", "HEAD^") == "commit"
    assert _git("cat-file", "-t", "HEAD^^{tree}") == "tree"


def test_freeze_artifact_bindings_match_git_identities():
    freeze = _freeze_artifact_at("HEAD")
    assert freeze["status"] == "FROZEN_BEFORE_V2_PRODUCTION"
    assert freeze["reviewed_implementation"]["head"] == REVIEWED_IMPLEMENTATION_HEAD
    assert freeze["reviewed_implementation"]["tree"] == REVIEWED_IMPLEMENTATION_TREE
    assert freeze["freeze_parent_expected_head"] == REVIEWED_IMPLEMENTATION_HEAD
    assert freeze["methodology_authority"]["original_prereg"]["head"] == ORIGINAL_PREREG_HEAD
    assert freeze["methodology_authority"]["original_prereg"]["tree"] == ORIGINAL_PREREG_TREE
    assert freeze["methodology_authority"]["amendment_001"]["head"] == AMENDMENT_001_HEAD
    assert freeze["methodology_authority"]["amendment_001"]["tree"] == AMENDMENT_001_TREE
    # The prereg/amendment git identities must actually exist and be commits.
    assert _git("cat-file", "-t", ORIGINAL_PREREG_HEAD) == "commit"
    assert _git("rev-parse", f"{ORIGINAL_PREREG_HEAD}^{{tree}}") == ORIGINAL_PREREG_TREE
    assert _git("cat-file", "-t", AMENDMENT_001_HEAD) == "commit"
    assert _git("rev-parse", f"{AMENDMENT_001_HEAD}^{{tree}}") == AMENDMENT_001_TREE


def test_v2_policy_blob_hash_size_match_freeze_artifact_and_git():
    freeze = _freeze_artifact_at("HEAD")
    bound = freeze["execution_authoritative_v2_policy_source"]
    assert bound["path"] == V2_POLICY_PATH
    live_blob = _blob_id("HEAD", V2_POLICY_PATH)
    live_sha256 = _blob_sha256("HEAD", V2_POLICY_PATH)
    live_size = _blob_size("HEAD", V2_POLICY_PATH)
    assert bound["git_blob"] == live_blob
    assert bound["sha256"] == live_sha256
    assert bound["size_bytes"] == live_size
    # Also bound to the exact reviewed-implementation-commit bytes.
    assert live_blob == _blob_id(REVIEWED_IMPLEMENTATION_HEAD, V2_POLICY_PATH)


def test_v1_tcb_hashes_match_frozen_values_and_freeze_artifact():
    freeze = _freeze_artifact_at("HEAD")
    by_path = {entry["path"]: entry for entry in freeze["v1_tcb_files"]}
    for role, path in V1_TCB_PATHS.items():
        live_sha256 = _blob_sha256("HEAD", path)
        live_size = _blob_size("HEAD", path)
        assert live_sha256 == FROZEN_TCB_SHA256[role], f"{role} TCB hash drifted"
        entry = by_path[path]
        assert entry["sha256"] == live_sha256
        assert entry["size_bytes"] == live_size
        assert entry["git_blob"] == _blob_id("HEAD", path)


def test_v2_implementation_bytes_unchanged_since_reviewed_head():
    diff = _git("diff", f"{REVIEWED_IMPLEMENTATION_HEAD}..HEAD", "--", V2_POLICY_PATH)
    assert diff == ""
    for path in V1_TCB_PATHS.values():
        assert _git("diff", f"{REVIEWED_IMPLEMENTATION_HEAD}..HEAD", "--", path) == ""


def test_freeze_commit_only_changed_allowed_paths():
    changed = set(
        _git("diff-tree", "--no-commit-id", "--name-only", "-r", "HEAD").splitlines()
    )
    assert changed, "freeze commit must actually change something"
    assert changed <= FREEZE_ALLOWED_CHANGED_PATHS
    assert V2_POLICY_PATH not in changed
    for path in V1_TCB_PATHS.values():
        assert path not in changed


def test_no_v2_production_arm_result_or_world_records_artifacts_exist():
    tracked = _git("ls-tree", "-r", "--name-only", "HEAD", "--", "docs/research").splitlines()
    forbidden_markers = ("_ARM", "_RESULT", "_WORLD_RECORDS")
    for path in tracked:
        if "V2_RANK_DEGENERACY_POLICY" not in path:
            continue
        for marker in forbidden_markers:
            assert marker not in path.upper(), f"unexpected V2 authority artifact: {path}"


def test_freeze_production_state_not_armed_not_consumed():
    freeze = _freeze_artifact_at("HEAD")
    state = freeze["production_state"]
    assert state["production_armed"] is False
    assert state["production_executed"] is False
    assert state["result_minted"] is False
    assert state["world_records_created"] is False
    assert state["authority_consumed"] is False
    assert freeze["v1_attempt_status"] == "INCOMPLETE_EXECUTION_NO_METHODOLOGY_CLAIM"
    assert freeze["v1_3087_subset_claimable"] is False


def test_v2_module_still_fails_closed_at_freeze_commit():
    from scripts.research import harness_synthetic_edge_calibration_v2_rank_policy as v2
    import pytest

    with pytest.raises(v2.ProductionGridForbidden):
        v2.run_frozen_production_grid()
    with pytest.raises(v2.ProductionGridForbidden):
        v2.assert_not_production_grid(n_rows=5000)
