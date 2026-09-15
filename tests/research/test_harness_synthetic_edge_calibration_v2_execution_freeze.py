"""Freeze verification for the new V2 execution implementation freeze.

These tests verify committed git object bytes, not the live worktree. They
must not run the frozen 3200-world grid, mint RESULT/WORLD_RECORDS, create an
ARM, consume a reservation, or evaluate a synthetic world. The freeze commit
under test binds a reviewed, already-closed runtime; it must not change any
execution-authoritative byte.

Unlike earlier freeze self-checks in this history, this file never assumes
``HEAD`` (or ``HEAD^``) IS the freeze commit. That assumption breaks the
moment any commit lands on top (an ARM, a later repair) -- which is exactly
what happened to two tests in
``test_harness_synthetic_edge_calibration_v2_33_33_post_wiring_runtime_freeze.py``
once this freeze's own implementation predecessor (baf9f23) was committed.
Instead, the freeze commit under test is located structurally: it is the
unique immediate child of the hardcoded, already-known IMPLEMENTATION_HEAD
on the ancestry path to whatever is currently checked out. This remains
correct no matter how many further descendant commits (an ARM, a future
repair) exist on top.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

IMPLEMENTATION_HEAD = "baf9f23045f4c19418eaaf3a9a7a1b69e21aff98"
IMPLEMENTATION_TREE = "bd7aee5db2e6194058196d96c8a054bca08d0b86"

HISTORICAL_33_33_IMPLEMENTATION_HEAD = "614295d4c0bf7a263bd2c6dc9a5c595e2c80055f"
HISTORICAL_33_33_IMPLEMENTATION_TREE = "e754b12f8db93db3109a30e3b4d476eb85803e04"
HISTORICAL_33_33_FREEZE_HEAD = "e50fceebfe83b82ea9de2f98954ee7ad6c9a4308"
HISTORICAL_33_33_FREEZE_TREE = "2f2b0943fffe143324da4c10545d560d6048079e"
HISTORICAL_33_33_FREEZE_ARTIFACT_SHA256 = (
    "89ca1ba0b416a4e2af07aa03d32b0ed2e9a9ec0ecee0327e3fda113c07ff74d7"
)
HISTORICAL_33_33_FREEZE_PATH = (
    "docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V2_33_33_IMPLEMENTATION_FREEZE.json"
)

HISTORICAL_POST_WIRING_IMPLEMENTATION_HEAD = "c1d6acc9f3db3b35f06a02d7fb2361b8d4ea69c5"
HISTORICAL_POST_WIRING_FREEZE_HEAD = "75f12bd31eac631a3baedd4a627344c0f2d40190"
HISTORICAL_POST_WIRING_FREEZE_TREE = "808c4cfa0849a79d730bcc057832fcae99e67f6a"
HISTORICAL_POST_WIRING_FREEZE_ARTIFACT_SHA256 = (
    "f3563cbef13305e601d5698a4ec5b1933e6531b2d18388647ffd814ed1199306"
)
HISTORICAL_POST_WIRING_FREEZE_PATH = (
    "docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V2_33_33_POST_WIRING_RUNTIME_FREEZE.json"
)

WIRING_REPAIR_HEAD = "84f4c566fcea106156c00cfea1a825f3a050946f"
WIRING_REPAIR_TREE = "82d4e2f4d41cc02bf4d6d9f3d819137633a97dfc"
LIVE_RUNTIME_REPAIR_HEAD = "c1d6acc9f3db3b35f06a02d7fb2361b8d4ea69c5"
LIVE_RUNTIME_REPAIR_TREE = "67f19c997d7480f77ef741e2e2715c06cf3e8fcd"
SELF_REFERENCE_REPAIR_HEAD = IMPLEMENTATION_HEAD
SELF_REFERENCE_REPAIR_TREE = IMPLEMENTATION_TREE

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
    "docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V2_EXECUTION_FREEZE.json"
)
FREEZE_DOCUMENT_PATH = (
    "docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V2_EXECUTION_FREEZE.md"
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
    "tests/research/test_harness_synthetic_edge_calibration_v2_execution_freeze.py",
    "docs/DOCUMENTATION_INDEX.md",
}

AUTHORITY_MUST_BE_UNCHANGED = (
    *IMPLEMENTATION_PATHS,
    V2_POLICY_PATH,
    V2_POLICY_FREEZE_PATH,
    HISTORICAL_33_33_FREEZE_PATH,
    HISTORICAL_POST_WIRING_FREEZE_PATH,
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


def _freeze_commit() -> str:
    """The freeze commit under test, located structurally rather than
    assumed to be ``HEAD``: the unique immediate child of the hardcoded,
    already-known IMPLEMENTATION_HEAD on the ancestry path to whatever is
    currently checked out. Robust to any number of further descendant
    commits (a future ARM, a future repair) landing on top -- unlike a bare
    ``git rev-parse HEAD^``, which silently starts validating the wrong
    commit the moment anything is committed after the freeze."""
    path = _git(
        "rev-list", "--ancestry-path", "--reverse", f"{IMPLEMENTATION_HEAD}..HEAD"
    ).splitlines()
    assert path, "current HEAD is not a descendant of IMPLEMENTATION_HEAD"
    freeze = path[0]
    assert _git("rev-parse", f"{freeze}^") == IMPLEMENTATION_HEAD
    return freeze


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


def _assert_bound_file(commit: str, bound: dict, *, identity_head: str) -> None:
    path = bound["path"]
    assert bound["git_blob"] == _blob_id(commit, path), path
    assert bound["sha256"] == _blob_sha256(commit, path), path
    assert bound["size_bytes"] == _blob_size(commit, path), path
    assert bound["git_blob"] == _blob_id(identity_head, path), path
    assert bound["sha256"] == _blob_sha256(identity_head, path), path


def test_freeze_parent_is_implementation_head_and_tree():
    freeze = _freeze_commit()
    assert _git("rev-parse", f"{freeze}^") == IMPLEMENTATION_HEAD
    assert _git("rev-parse", f"{freeze}^^{{tree}}") == IMPLEMENTATION_TREE
    assert _git("rev-parse", f"{freeze}^{{tree}}") is not None


def test_freeze_artifact_does_not_circularly_self_hash():
    freeze_commit = _freeze_commit()
    freeze = _freeze_artifact_at(freeze_commit)
    assert freeze["freeze_commit_head"] == "UNSET_UNTIL_THIS_COMMIT"
    assert freeze["freeze_commit_tree"] == "UNSET_UNTIL_THIS_COMMIT"
    encoded = json.dumps(freeze)
    artifact_sha = _blob_sha256(freeze_commit, FREEZE_ARTIFACT_PATH)
    assert artifact_sha not in encoded


def test_worktree_tamper_does_not_change_git_object_verification(tmp_path):
    freeze_commit = _freeze_commit()
    freeze = _freeze_artifact_at(freeze_commit)
    artifact_path = REPO / FREEZE_ARTIFACT_PATH
    original = artifact_path.read_bytes()
    try:
        artifact_path.write_bytes(original + b"\n")
        reread = _freeze_artifact_at(freeze_commit)
        assert reread == freeze
        assert _blob_sha256(freeze_commit, FREEZE_ARTIFACT_PATH) == hashlib.sha256(original).hexdigest()
    finally:
        artifact_path.write_bytes(original)


def test_freeze_artifact_bindings_match_git_identities():
    freeze_commit = _freeze_commit()
    freeze = _freeze_artifact_at(freeze_commit)
    assert freeze["status"] == "FROZEN_BEFORE_V2_PRODUCTION"
    assert freeze["implementation_review_verdict"] == "GO_FOR_NEW_IMPLEMENTATION_FREEZE"
    assert freeze["reviewed_implementation"]["head"] == IMPLEMENTATION_HEAD
    assert freeze["reviewed_implementation"]["tree"] == IMPLEMENTATION_TREE
    assert freeze["freeze_parent_expected_head"] == IMPLEMENTATION_HEAD

    distinction = freeze["authority_distinction"]
    assert distinction["historical_33_33_freeze_valid"] is True
    assert distinction["historical_33_33_freeze_binds_implementation"] == (
        HISTORICAL_33_33_IMPLEMENTATION_HEAD
    )
    assert distinction["historical_post_wiring_freeze_valid"] is True
    assert distinction["historical_post_wiring_freeze_binds_implementation"] == (
        HISTORICAL_POST_WIRING_IMPLEMENTATION_HEAD
    )
    assert distinction["historical_post_wiring_freeze_sufficient_for_current_runtime"] is False
    assert distinction["current_execution_freeze_binds_implementation"] == IMPLEMENTATION_HEAD

    repairs = {entry["head"]: entry for entry in freeze["authorization_repair_provenance"]}
    assert repairs[WIRING_REPAIR_HEAD]["tree"] == WIRING_REPAIR_TREE
    assert repairs[LIVE_RUNTIME_REPAIR_HEAD]["tree"] == LIVE_RUNTIME_REPAIR_TREE
    assert repairs[SELF_REFERENCE_REPAIR_HEAD]["tree"] == SELF_REFERENCE_REPAIR_TREE

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
        ("wiring_repair", WIRING_REPAIR_HEAD, WIRING_REPAIR_TREE),
        ("live_runtime_repair", LIVE_RUNTIME_REPAIR_HEAD, LIVE_RUNTIME_REPAIR_TREE),
        ("implementation", IMPLEMENTATION_HEAD, IMPLEMENTATION_TREE),
        ("historical_33_33_impl", HISTORICAL_33_33_IMPLEMENTATION_HEAD, HISTORICAL_33_33_IMPLEMENTATION_TREE),
        ("historical_33_33_freeze", HISTORICAL_33_33_FREEZE_HEAD, HISTORICAL_33_33_FREEZE_TREE),
        (
            "historical_post_wiring_impl",
            HISTORICAL_POST_WIRING_IMPLEMENTATION_HEAD,
            LIVE_RUNTIME_REPAIR_TREE,
        ),
        (
            "historical_post_wiring_freeze",
            HISTORICAL_POST_WIRING_FREEZE_HEAD,
            HISTORICAL_POST_WIRING_FREEZE_TREE,
        ),
    ):
        assert _git("cat-file", "-t", head) == "commit", label
        assert _git("rev-parse", f"{head}^{{tree}}") == tree, label

    policy = freeze["v2_rank_policy_authority"]
    assert policy["reviewed_implementation_head"] == V2_POLICY_REVIEWED_HEAD
    assert policy["reviewed_implementation_tree"] == V2_POLICY_REVIEWED_TREE
    assert policy["freeze_head"] == V2_POLICY_FREEZE_HEAD
    assert policy["freeze_tree"] == V2_POLICY_FREEZE_TREE
    assert _git("rev-parse", f"{V2_POLICY_FREEZE_HEAD}^{{tree}}") == V2_POLICY_FREEZE_TREE


def test_historical_freezes_identity_preserved_and_not_rewritten():
    freeze_commit = _freeze_commit()
    freeze = _freeze_artifact_at(freeze_commit)
    by_role = {entry["role"]: entry for entry in freeze["historical_freezes"]}

    hist_33_33 = by_role["HISTORICAL_33_33_IMPLEMENTATION_FREEZE"]
    assert hist_33_33["head"] == HISTORICAL_33_33_FREEZE_HEAD
    assert hist_33_33["tree"] == HISTORICAL_33_33_FREEZE_TREE
    assert hist_33_33["reviewed_implementation_head"] == HISTORICAL_33_33_IMPLEMENTATION_HEAD
    assert hist_33_33["still_historically_valid"] is True
    assert hist_33_33["rewritten_by_this_unit"] is False
    _assert_bound_file(
        freeze_commit, hist_33_33["freeze_artifact"], identity_head=HISTORICAL_33_33_FREEZE_HEAD
    )
    assert hist_33_33["freeze_artifact"]["sha256"] == HISTORICAL_33_33_FREEZE_ARTIFACT_SHA256

    hist_post_wiring = by_role["HISTORICAL_POST_WIRING_RUNTIME_FREEZE"]
    assert hist_post_wiring["head"] == HISTORICAL_POST_WIRING_FREEZE_HEAD
    assert hist_post_wiring["tree"] == HISTORICAL_POST_WIRING_FREEZE_TREE
    assert hist_post_wiring["reviewed_implementation_head"] == HISTORICAL_POST_WIRING_IMPLEMENTATION_HEAD
    assert hist_post_wiring["still_historically_valid"] is True
    assert hist_post_wiring["rewritten_by_this_unit"] is False
    _assert_bound_file(
        freeze_commit,
        hist_post_wiring["freeze_artifact"],
        identity_head=HISTORICAL_POST_WIRING_FREEZE_HEAD,
    )
    assert (
        hist_post_wiring["freeze_artifact"]["sha256"]
        == HISTORICAL_POST_WIRING_FREEZE_ARTIFACT_SHA256
    )

    # Neither historical freeze document was rewritten by this new freeze
    # commit: byte-identical between the historical commit and this one.
    assert _git("diff", f"{HISTORICAL_33_33_FREEZE_HEAD}..{freeze_commit}", "--", HISTORICAL_33_33_FREEZE_PATH) == ""
    assert (
        _git(
            "diff",
            f"{HISTORICAL_POST_WIRING_FREEZE_HEAD}..{freeze_commit}",
            "--",
            HISTORICAL_POST_WIRING_FREEZE_PATH,
        )
        == ""
    )


def test_frozen_implementation_blobs_match_reviewed_commit_and_artifact():
    freeze_commit = _freeze_commit()
    freeze = _freeze_artifact_at(freeze_commit)
    by_path = {
        entry["path"]: entry
        for entry in freeze["execution_authoritative_implementation_sources"]
    }
    assert set(by_path) == set(IMPLEMENTATION_PATHS)
    for path in IMPLEMENTATION_PATHS:
        _assert_bound_file(freeze_commit, by_path[path], identity_head=IMPLEMENTATION_HEAD)


def test_ladder_unchanged_production_changed_since_historical_33_33():
    freeze_commit = _freeze_commit()
    freeze = _freeze_artifact_at(freeze_commit)
    by_path = {
        entry["path"]: entry
        for entry in freeze["execution_authoritative_implementation_sources"]
    }
    assert by_path[LADDER_PATH]["unchanged_since_historical_33_33_implementation"] is True
    assert by_path[PRODUCTION_PATH]["unchanged_since_historical_33_33_implementation"] is False
    assert _blob_id(freeze_commit, LADDER_PATH) == _blob_id(
        HISTORICAL_33_33_IMPLEMENTATION_HEAD, LADDER_PATH
    )
    assert _blob_id(freeze_commit, PRODUCTION_PATH) != _blob_id(
        HISTORICAL_33_33_IMPLEMENTATION_HEAD, PRODUCTION_PATH
    )
    assert _blob_id(freeze_commit, PRODUCTION_PATH) != _blob_id(
        HISTORICAL_POST_WIRING_IMPLEMENTATION_HEAD, PRODUCTION_PATH
    )


def test_frozen_v2_policy_and_freeze_artifact_unchanged():
    freeze_commit = _freeze_commit()
    freeze = _freeze_artifact_at(freeze_commit)
    policy = freeze["v2_rank_policy_authority"]
    _assert_bound_file(
        freeze_commit,
        policy["execution_authoritative_v2_policy_source"],
        identity_head=IMPLEMENTATION_HEAD,
    )
    _assert_bound_file(
        freeze_commit, policy["freeze_artifact"], identity_head=V2_POLICY_FREEZE_HEAD
    )
    assert policy["execution_authoritative_v2_policy_source"]["path"] == V2_POLICY_PATH
    assert policy["freeze_artifact"]["path"] == V2_POLICY_FREEZE_PATH


def test_governing_amendment_hashes_match_frozen_values():
    freeze_commit = _freeze_commit()
    freeze = _freeze_artifact_at(freeze_commit)
    method = freeze["methodology_authority"]
    for bound in method["amendment_003"]["files"]:
        _assert_bound_file(freeze_commit, bound, identity_head=IMPLEMENTATION_HEAD)
        assert bound["sha256"] == FROZEN_AMENDMENT_003_SHA256[bound["path"]]
    for bound in method["amendment_004"]["files"]:
        _assert_bound_file(freeze_commit, bound, identity_head=IMPLEMENTATION_HEAD)
        assert bound["sha256"] == FROZEN_AMENDMENT_004_SHA256[bound["path"]]
    for bound in method["amendment_002"]["files"]:
        _assert_bound_file(freeze_commit, bound, identity_head=IMPLEMENTATION_HEAD)
    for bound in method["original_prereg"]["files"]:
        _assert_bound_file(freeze_commit, bound, identity_head=IMPLEMENTATION_HEAD)
    for bound in method["amendment_001"]["files"]:
        _assert_bound_file(freeze_commit, bound, identity_head=IMPLEMENTATION_HEAD)


def test_v1_tcb_hashes_match_frozen_values_and_freeze_artifact():
    freeze_commit = _freeze_commit()
    freeze = _freeze_artifact_at(freeze_commit)
    by_path = {entry["path"]: entry for entry in freeze["v1_tcb_files"]}
    for role, path in V1_TCB_PATHS.items():
        live_sha256 = _blob_sha256(freeze_commit, path)
        live_size = _blob_size(freeze_commit, path)
        assert live_sha256 == FROZEN_TCB_SHA256[role], f"{role} TCB hash drifted"
        entry = by_path[path]
        assert entry["sha256"] == live_sha256
        assert entry["size_bytes"] == live_size
        assert entry["git_blob"] == _blob_id(freeze_commit, path)
        assert live_sha256 == _blob_sha256(IMPLEMENTATION_HEAD, path)
        assert live_sha256 == _blob_sha256(HISTORICAL_33_33_IMPLEMENTATION_HEAD, path)


def test_canonical_v2_plan_identity_matches_freeze_artifact():
    freeze_commit = _freeze_commit()
    freeze = _freeze_artifact_at(freeze_commit)
    plan = freeze["canonical_v2_plan"]
    assert plan["sha256"] == CANONICAL_V2_PLAN_SHA256
    assert plan["world_count"] == CANONICAL_WORLD_COUNT
    from scripts.research.harness_synthetic_edge_calibration_v2_production import (
        canonical_v2_plan,
        canonical_v2_world_count,
    )

    live = canonical_v2_plan(repo_root=REPO, commit=freeze_commit)
    implementation = canonical_v2_plan(repo_root=REPO, commit=IMPLEMENTATION_HEAD)
    historical = canonical_v2_plan(repo_root=REPO, commit=HISTORICAL_33_33_IMPLEMENTATION_HEAD)
    assert live["sha256"] == CANONICAL_V2_PLAN_SHA256
    assert implementation["sha256"] == CANONICAL_V2_PLAN_SHA256
    assert historical["sha256"] == CANONICAL_V2_PLAN_SHA256
    assert canonical_v2_world_count() == CANONICAL_WORLD_COUNT


def test_authority_bytes_unchanged_since_implementation():
    freeze_commit = _freeze_commit()
    for path in AUTHORITY_MUST_BE_UNCHANGED:
        assert _git("diff", f"{IMPLEMENTATION_HEAD}..{freeze_commit}", "--", path) == ""


def test_freeze_commit_only_changed_allowed_paths():
    freeze_commit = _freeze_commit()
    changed = set(
        _git("diff-tree", "--no-commit-id", "--name-only", "-r", freeze_commit).splitlines()
    )
    assert changed, "freeze commit must actually change something"
    assert changed <= FREEZE_ALLOWED_CHANGED_PATHS
    for path in AUTHORITY_MUST_BE_UNCHANGED:
        assert path not in changed


def test_no_v2_production_arm_result_or_world_records_artifacts_exist():
    freeze_commit = _freeze_commit()
    tracked = _git("ls-tree", "-r", "--name-only", freeze_commit, "--", "docs/research").splitlines()
    forbidden_markers = ("_ARM", "_RESULT", "_WORLD_RECORDS", "_RESERVATION", "_CLAIM")
    for path in tracked:
        if "V2_RANK_DEGENERACY_POLICY" not in path and "V2_33_33" not in path and "V2_EXECUTION" not in path:
            continue
        for marker in forbidden_markers:
            assert marker not in path.upper(), f"unexpected V2 authority artifact: {path}"


def test_freeze_production_state_not_armed_not_consumed():
    freeze_commit = _freeze_commit()
    freeze = _freeze_artifact_at(freeze_commit)
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
    assert freeze["this_freeze_does_not"]["create_arm"] is True
    assert freeze["this_freeze_does_not"]["authorize_execution"] is True
    assert freeze["this_freeze_does_not"]["rewrite_historical_33_33_freeze"] is True
    assert freeze["this_freeze_does_not"]["rewrite_historical_post_wiring_freeze"] is True
    assert freeze["this_freeze_does_not"]["claim_any_historical_freeze_invalid"] is True


def test_visibility_and_minors_recorded_unrepaired():
    freeze_commit = _freeze_commit()
    freeze = _freeze_artifact_at(freeze_commit)
    vis = freeze["visibility_limitation"]
    assert vis["status"] == "UNRESOLVED_FAIL_CLOSED"
    assert vis["sentinel"] == "V2VisibilityStatisticUnavailable"
    assert vis["resolved_in_this_freeze"] is False
    by_id = {entry["id"]: entry for entry in freeze["known_non_blocking_limitations"]}
    assert by_id["MINOR-1"]["repaired_in_this_freeze"] is False
    assert "memoization" in by_id["MINOR-1"]["summary"]
    assert by_id["MINOR-2"]["repaired_in_this_freeze"] is False
    assert "FINAL_OVERALL" in by_id["MINOR-2"]["summary"]
    assert by_id["PREEXISTING-DIRECT-ENTRYPOINT-RESERVATION"]["repaired_in_this_freeze"] is False
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


def test_freeze_accepted_as_candidate_by_repaired_runtime():
    """RUNTIME CONSUMABILITY CHECK: the actual repaired baf9f23 runtime must
    recognize this freeze commit as a valid candidate freeze -- the exact
    property the historical post-wiring freeze (75f12bd) lacked. Uses the
    real ``_authenticate_v2_execution_freeze`` against real committed git
    objects; no monkeypatching."""
    from scripts.research import harness_synthetic_edge_calibration_v2_production as v2p

    freeze_commit = _freeze_commit()
    authenticated = v2p._authenticate_v2_execution_freeze(REPO, freeze_commit)
    assert authenticated is not None
    assert authenticated["reviewed_implementation"]["head"] == IMPLEMENTATION_HEAD


def test_future_arm_can_bind_this_freeze_without_runtime_edit(tmp_path):
    """A disposable ARM, committed as this freeze's immediate child in a
    throwaway clone, authorizes using the real, unmodified runtime -- no
    edit to production.py at any point. Nothing here is pushed or affects
    canonical history."""
    import subprocess as sp
    from unittest import mock

    from scripts.research import harness_synthetic_edge_calibration_v2_production as v2p

    freeze_commit = _freeze_commit()
    repo = tmp_path / "disposable_arm_probe"
    sp.run(["git", "clone", "--local", "--", str(REPO), str(repo)], check=True, capture_output=True)
    sp.run(["git", "-C", str(repo), "checkout", "-q", freeze_commit], check=True, capture_output=True)
    sp.run(["git", "-C", str(repo), "config", "user.email", "probe@example.com"], check=True)
    sp.run(["git", "-C", str(repo), "config", "user.name", "probe"], check=True)
    sp.run(["git", "-C", str(repo), "config", "commit.gpgsign", "false"], check=True)

    payload = dict(v2p.V2_ARM_REQUIRED_LITERALS)
    payload.update(v2p.required_v2_arm_binding_fields(repo, freeze_commit))
    (repo / v2p.CANONICAL_V2_ARM_PATH).write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    sp.run(["git", "-C", str(repo), "add", "-A"], check=True)
    sp.run(["git", "-C", str(repo), "commit", "-q", "-m", "disposable arm probe (not pushed)"], check=True)

    assert v2p.v2_production_arm_authorized(repo_root=repo) is True
