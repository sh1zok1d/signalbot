"""Freeze verification for the reviewed V2 33/33 implementation.

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

REVIEWED_IMPLEMENTATION_HEAD = "614295d4c0bf7a263bd2c6dc9a5c595e2c80055f"
REVIEWED_IMPLEMENTATION_TREE = "e754b12f8db93db3109a30e3b4d476eb85803e04"
FREEZE_HEAD = "e50fceebfe83b82ea9de2f98954ee7ad6c9a4308"
FREEZE_TREE = "2f2b0943fffe143324da4c10545d560d6048079e"

ORIGINAL_PREREG_HEAD = "ada237edc330b44bc412332e263f124757919e93"
ORIGINAL_PREREG_TREE = "ba1c0873879b7ea8556c3e238f8b962b91da6dc2"

AMENDMENT_001_HEAD = "d8f0a996bc4341d0cbe01a1a061130b889ed5e75"
AMENDMENT_001_TREE = "09dca9b1240a43d5de9de0dadf32d27e00e7eaea"

AMENDMENT_002_HEAD = "f84607594f4459f8ee1cbd14a7ab16294d586301"
AMENDMENT_002_TREE = "810f0a987e4a3dda1fc128905772727c0dcafee9"

AMENDMENT_003_HEAD = "dfba85d2bfbb4bc3f9f3c34ea87dc3ae82a2dd18"
AMENDMENT_003_TREE = "c0b4c00dd701eb262de021f34481161a7afe1f6f"

AMENDMENT_004_HEAD = "df5dcde63581198d4766fa662de89eae3e7c461e"
AMENDMENT_004_TREE = "95814ae17922c399350200a4f2b55b1021113442"

V2_POLICY_REVIEWED_HEAD = "a310837bab4ee60c7495cca3bdb476abdc58a041"
V2_POLICY_REVIEWED_TREE = "b15c4102b01514ff73e1728aec072eda9b528815"
V2_POLICY_FREEZE_HEAD = "f96197d109fc22c12e4c8ba19715d67c65187c0e"
V2_POLICY_FREEZE_TREE = "ec169d8bd73896308ce4dcf1d5d5fd218cd55bd5"

CANONICAL_V2_PLAN_SHA256 = (
    "7fa12fd3b939cd210a69da37659fd1013a1dba43aca4c06abb6f5a6442a33800"
)
CANONICAL_WORLD_COUNT = 3200

LADDER_PATH = "scripts/research/harness_synthetic_edge_calibration_v2_inherited_ladder.py"
PRODUCTION_PATH = "scripts/research/harness_synthetic_edge_calibration_v2_production.py"
V2_POLICY_PATH = "scripts/research/harness_synthetic_edge_calibration_v2_rank_policy.py"
V2_POLICY_FREEZE_PATH = (
    "docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V2_RANK_DEGENERACY_POLICY_IMPLEMENTATION_FREEZE.json"
)

FREEZE_ARTIFACT_PATH = (
    "docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V2_33_33_IMPLEMENTATION_FREEZE.json"
)
FREEZE_DOCUMENT_PATH = (
    "docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V2_33_33_IMPLEMENTATION_FREEZE.md"
)

IMPLEMENTATION_PATHS = (LADDER_PATH, PRODUCTION_PATH)

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

FROZEN_AMENDMENT_003_SHA256 = {
    "docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V2_INHERITED_LADDER_AMENDMENT_003.md": (
        "10f26bbaeca30d47051026878ca8afd6622efdb8cc30562e44a7860abe896300"
    ),
    "docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V2_INHERITED_LADDER_AMENDMENT_003.json": (
        "f9856e8ed957bf9ed800121ef17c9c73223eee3bc4af2711130f19bf1a59b7db"
    ),
}
FROZEN_AMENDMENT_004_SHA256 = {
    "docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V2_INHERITED_LADDER_AMENDMENT_004.md": (
        "9002838f4dc14a27a5f83870abb7cad4bd83a5c84abc75723263562045f646ca"
    ),
    "docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V2_INHERITED_LADDER_AMENDMENT_004.json": (
        "8c3f9d2d662e5ce807baf4b65f94c145ed84c7337c41653493867d25e6a4ea55"
    ),
}

FREEZE_ALLOWED_CHANGED_PATHS = {
    FREEZE_ARTIFACT_PATH,
    FREEZE_DOCUMENT_PATH,
    "tests/research/test_harness_synthetic_edge_calibration_v2_33_33_implementation_freeze.py",
    "docs/PROJECT_STATUS.md",
    "docs/RESEARCH_LEDGER.md",
    "docs/RESEARCH_ROADMAP.md",
    "docs/DOCUMENTATION_INDEX.md",
}

AUTHORITY_MUST_BE_UNCHANGED = (
    *IMPLEMENTATION_PATHS,
    V2_POLICY_PATH,
    V2_POLICY_FREEZE_PATH,
    *V1_TCB_PATHS.values(),
    *FROZEN_AMENDMENT_003_SHA256,
    *FROZEN_AMENDMENT_004_SHA256,
    "docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V2_RANK_DEGENERACY_POLICY_PREREG.md",
    "docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V2_RANK_DEGENERACY_POLICY_PREREG.json",
    "docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V2_RANK_DEGENERACY_POLICY_PREREG_AMENDMENT_001.md",
    "docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V2_RANK_DEGENERACY_POLICY_PREREG_AMENDMENT_001.json",
    "docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V2_INHERITED_LADDER_AMENDMENT_002.md",
    "docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V2_INHERITED_LADDER_AMENDMENT_002.json",
)


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


def _assert_bound_file(commit: str, bound: dict) -> None:
    path = bound["path"]
    assert bound["git_blob"] == _blob_id(commit, path), path
    assert bound["sha256"] == _blob_sha256(commit, path), path
    assert bound["size_bytes"] == _blob_size(commit, path), path
    assert bound["git_blob"] == _blob_id(REVIEWED_IMPLEMENTATION_HEAD, path), path
    assert bound["sha256"] == _blob_sha256(REVIEWED_IMPLEMENTATION_HEAD, path), path


def test_freeze_parent_is_reviewed_implementation_head_and_tree():
    parent = _git("rev-parse", f"{FREEZE_HEAD}^")
    parent_tree = _git("rev-parse", f"{FREEZE_HEAD}^^{{tree}}")
    freeze_tree = _git("rev-parse", f"{FREEZE_HEAD}^{{tree}}")
    assert parent == REVIEWED_IMPLEMENTATION_HEAD
    assert parent_tree == REVIEWED_IMPLEMENTATION_TREE
    assert freeze_tree == FREEZE_TREE


def test_starting_worktree_was_clean_before_freeze():
    assert _git("cat-file", "-t", f"{FREEZE_HEAD}^") == "commit"
    assert _git("cat-file", "-t", f"{FREEZE_HEAD}^^{{tree}}") == "tree"


def test_freeze_artifact_does_not_circularly_self_hash():
    freeze = _freeze_artifact_at(FREEZE_HEAD)
    assert freeze["freeze_commit_head"] == "UNSET_UNTIL_THIS_COMMIT"
    assert freeze["freeze_commit_tree"] == "UNSET_UNTIL_THIS_COMMIT"
    encoded = json.dumps(freeze)
    artifact_sha = _blob_sha256(FREEZE_HEAD, FREEZE_ARTIFACT_PATH)
    assert artifact_sha not in encoded


def test_freeze_artifact_bindings_match_git_identities():
    freeze = _freeze_artifact_at(FREEZE_HEAD)
    assert freeze["status"] == "FROZEN_BEFORE_V2_PRODUCTION"
    assert freeze["implementation_review_verdict"] == "GO_FOR_IMPLEMENTATION_FREEZE"
    assert freeze["reviewed_implementation"]["head"] == REVIEWED_IMPLEMENTATION_HEAD
    assert freeze["reviewed_implementation"]["tree"] == REVIEWED_IMPLEMENTATION_TREE
    assert freeze["freeze_parent_expected_head"] == REVIEWED_IMPLEMENTATION_HEAD

    method = freeze["methodology_authority"]
    assert method["original_prereg"]["head"] == ORIGINAL_PREREG_HEAD
    assert method["original_prereg"]["tree"] == ORIGINAL_PREREG_TREE
    assert method["amendment_001"]["head"] == AMENDMENT_001_HEAD
    assert method["amendment_001"]["tree"] == AMENDMENT_001_TREE
    assert method["amendment_002"]["head"] == AMENDMENT_002_HEAD
    assert method["amendment_002"]["tree"] == AMENDMENT_002_TREE
    assert method["amendment_002"]["status"] == "REJECTED_HISTORICAL_AUTHORITY"
    assert method["amendment_002"]["governs_executable_science"] is False
    assert method["amendment_003"]["head"] == AMENDMENT_003_HEAD
    assert method["amendment_003"]["tree"] == AMENDMENT_003_TREE
    assert method["amendment_003"]["governs_executable_science"] is True
    assert method["amendment_004"]["head"] == AMENDMENT_004_HEAD
    assert method["amendment_004"]["tree"] == AMENDMENT_004_TREE
    assert method["amendment_004"]["governs_executable_science"] is True
    assert method["approved_methodology_head"] == AMENDMENT_004_HEAD
    assert method["approved_methodology_tree"] == AMENDMENT_004_TREE

    for label, head, tree in (
        ("original_prereg", ORIGINAL_PREREG_HEAD, ORIGINAL_PREREG_TREE),
        ("amendment_001", AMENDMENT_001_HEAD, AMENDMENT_001_TREE),
        ("amendment_002", AMENDMENT_002_HEAD, AMENDMENT_002_TREE),
        ("amendment_003", AMENDMENT_003_HEAD, AMENDMENT_003_TREE),
        ("amendment_004", AMENDMENT_004_HEAD, AMENDMENT_004_TREE),
    ):
        assert _git("cat-file", "-t", head) == "commit", label
        assert _git("rev-parse", f"{head}^{{tree}}") == tree, label

    policy = freeze["v2_rank_policy_authority"]
    assert policy["reviewed_implementation_head"] == V2_POLICY_REVIEWED_HEAD
    assert policy["reviewed_implementation_tree"] == V2_POLICY_REVIEWED_TREE
    assert policy["freeze_head"] == V2_POLICY_FREEZE_HEAD
    assert policy["freeze_tree"] == V2_POLICY_FREEZE_TREE
    assert _git("rev-parse", f"{V2_POLICY_FREEZE_HEAD}^{{tree}}") == V2_POLICY_FREEZE_TREE


def test_frozen_implementation_blobs_match_reviewed_commit_and_artifact():
    freeze = _freeze_artifact_at(FREEZE_HEAD)
    by_path = {
        entry["path"]: entry
        for entry in freeze["execution_authoritative_implementation_sources"]
    }
    assert set(by_path) == set(IMPLEMENTATION_PATHS)
    for path in IMPLEMENTATION_PATHS:
        _assert_bound_file(FREEZE_HEAD, by_path[path])


def test_frozen_v2_policy_and_freeze_artifact_unchanged():
    freeze = _freeze_artifact_at(FREEZE_HEAD)
    policy = freeze["v2_rank_policy_authority"]
    _assert_bound_file(FREEZE_HEAD, policy["execution_authoritative_v2_policy_source"])
    _assert_bound_file(FREEZE_HEAD, policy["freeze_artifact"])
    assert policy["execution_authoritative_v2_policy_source"]["path"] == V2_POLICY_PATH
    assert policy["freeze_artifact"]["path"] == V2_POLICY_FREEZE_PATH


def test_governing_amendment_hashes_match_frozen_values():
    freeze = _freeze_artifact_at(FREEZE_HEAD)
    method = freeze["methodology_authority"]
    for bound in method["amendment_003"]["files"]:
        _assert_bound_file(FREEZE_HEAD, bound)
        assert bound["sha256"] == FROZEN_AMENDMENT_003_SHA256[bound["path"]]
    for bound in method["amendment_004"]["files"]:
        _assert_bound_file(FREEZE_HEAD, bound)
        assert bound["sha256"] == FROZEN_AMENDMENT_004_SHA256[bound["path"]]
    for bound in method["amendment_002"]["files"]:
        _assert_bound_file(FREEZE_HEAD, bound)
    for bound in method["original_prereg"]["files"]:
        _assert_bound_file(FREEZE_HEAD, bound)
    for bound in method["amendment_001"]["files"]:
        _assert_bound_file(FREEZE_HEAD, bound)


def test_v1_tcb_hashes_match_frozen_values_and_freeze_artifact():
    freeze = _freeze_artifact_at(FREEZE_HEAD)
    by_path = {entry["path"]: entry for entry in freeze["v1_tcb_files"]}
    for role, path in V1_TCB_PATHS.items():
        live_sha256 = _blob_sha256("HEAD", path)
        live_size = _blob_size("HEAD", path)
        assert live_sha256 == FROZEN_TCB_SHA256[role], f"{role} TCB hash drifted"
        entry = by_path[path]
        assert entry["sha256"] == live_sha256
        assert entry["size_bytes"] == live_size
        assert entry["git_blob"] == _blob_id("HEAD", path)
        assert live_sha256 == _blob_sha256(REVIEWED_IMPLEMENTATION_HEAD, path)


def test_canonical_v2_plan_identity_matches_freeze_artifact():
    freeze = _freeze_artifact_at(FREEZE_HEAD)
    plan = freeze["canonical_v2_plan"]
    assert plan["sha256"] == CANONICAL_V2_PLAN_SHA256
    assert plan["world_count"] == CANONICAL_WORLD_COUNT
    from scripts.research.harness_synthetic_edge_calibration_v2_production import (
        canonical_v2_plan,
        canonical_v2_world_count,
    )

    live = canonical_v2_plan(repo_root=REPO, commit="HEAD")
    reviewed = canonical_v2_plan(
        repo_root=REPO, commit=REVIEWED_IMPLEMENTATION_HEAD
    )
    assert live["sha256"] == CANONICAL_V2_PLAN_SHA256
    assert reviewed["sha256"] == CANONICAL_V2_PLAN_SHA256
    assert canonical_v2_world_count() == CANONICAL_WORLD_COUNT


def test_authority_bytes_unchanged_since_reviewed_head():
    for path in AUTHORITY_MUST_BE_UNCHANGED:
        assert _git("diff", f"{REVIEWED_IMPLEMENTATION_HEAD}..{FREEZE_HEAD}", "--", path) == ""


def test_freeze_commit_only_changed_allowed_paths():
    changed = set(
        _git("diff-tree", "--no-commit-id", "--name-only", "-r", FREEZE_HEAD).splitlines()
    )
    assert changed, "freeze commit must actually change something"
    assert changed <= FREEZE_ALLOWED_CHANGED_PATHS
    for path in AUTHORITY_MUST_BE_UNCHANGED:
        assert path not in changed


def test_no_v2_production_arm_result_or_world_records_artifacts_exist():
    tracked = _git("ls-tree", "-r", "--name-only", "HEAD", "--", "docs/research").splitlines()
    forbidden_markers = ("_ARM", "_RESULT", "_WORLD_RECORDS", "_RESERVATION", "_CLAIM")
    for path in tracked:
        if "V2_RANK_DEGENERACY_POLICY" not in path and "V2_33_33" not in path:
            continue
        for marker in forbidden_markers:
            assert marker not in path.upper(), f"unexpected V2 authority artifact: {path}"


def test_freeze_production_state_not_armed_not_consumed():
    freeze = _freeze_artifact_at(FREEZE_HEAD)
    state = freeze["production_state"]
    assert state["production_armed"] is False
    assert state["production_executed"] is False
    assert state["result_minted"] is False
    assert state["world_records_created"] is False
    assert state["authority_consumed"] is False
    assert state["arm_created"] is False
    assert state["execution_authorized"] is False
    assert state["canonical_3200_run_started"] is False
    assert freeze["v1_attempt_status"] == "INCOMPLETE_EXECUTION_NO_METHODOLOGY_CLAIM"
    assert freeze["v1_3087_subset_claimable"] is False


def test_visibility_and_minors_recorded_unrepaired():
    freeze = _freeze_artifact_at(FREEZE_HEAD)
    vis = freeze["visibility_limitation"]
    assert vis["status"] == "UNRESOLVED_FAIL_CLOSED"
    assert vis["sentinel"] == "V2VisibilityStatisticUnavailable"
    assert vis["resolved_in_this_freeze"] is False
    by_id = {entry["id"]: entry for entry in freeze["known_non_blocking_limitations"]}
    assert by_id["MINOR-1"]["repaired_in_this_freeze"] is False
    assert "memoization" in by_id["MINOR-1"]["summary"]
    assert by_id["MINOR-2"]["repaired_in_this_freeze"] is False
    assert "FINAL_OVERALL" in by_id["MINOR-2"]["summary"]
    assert freeze["this_freeze_does_not"]["create_arm"] is True
    assert freeze["this_freeze_does_not"]["authorize_execution"] is True
    assert freeze["this_freeze_does_not"]["run_canonical_3200"] is True
    assert freeze["this_freeze_does_not"]["resolve_visibility_gap"] is True
    assert freeze["this_freeze_does_not"]["repair_minor_1"] is True
    assert freeze["this_freeze_does_not"]["repair_minor_2"] is True


def test_v2_production_still_unarmed_and_visibility_fail_closed():
    from scripts.research import harness_synthetic_edge_calibration_v2_production as v2p
    from scripts.research.harness_synthetic_edge_calibration_v2_inherited_ladder import (
        V2VisibilityStatisticUnavailable,
    )
    import pytest

    assert v2p.v2_production_arm_authorized() is False
    with pytest.raises(v2p.V2ProductionNotArmed):
        v2p.run_canonical_v2_production_grid()
    assert issubclass(V2VisibilityStatisticUnavailable, Exception)
