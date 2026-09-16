"""Freeze verification for the V2 confirmatory-power control-calibration runtime.

These tests verify committed git object bytes. They must not run the frozen
3200-world grid, mint RESULT/WORLD_RECORDS, create a reservation, or evaluate
a synthetic world. The freeze commit under test is located structurally as
the unique immediate child of IMPLEMENTATION_HEAD on the ancestry path to
HEAD, so an ARM committed on top does not retarget these checks.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

IMPLEMENTATION_HEAD = "8917c776ac8c148828bfab4395fd84890ff3c847"
IMPLEMENTATION_TREE = "15664b6a47b7196fcd230619e134f6a89feec23e"

HISTORICAL_ARM_HEAD = "18ebb4c5629e1717a6633ee6bd63cda7c0bb65ea"
HISTORICAL_FREEZE_HEAD = "2523b389e10585c81e18a69f43cc1e38fface41f"
HISTORICAL_PLAN_SHA256 = (
    "7fa12fd3b939cd210a69da37659fd1013a1dba43aca4c06abb6f5a6442a33800"
)
HISTORICAL_RUN_IDENTITY = (
    "2088e76f99685c36e65387117b6f8a49482b3b68939f01d827023e0d36991818"
)

CANONICAL_V2_PLAN_SHA256 = (
    "b0ed15534ef0cf45f1232baa0d7c1881fb3a8aaa086477d67a5ab7e9198c677f"
)
CANONICAL_WORLD_COUNT = 3200
V1_PLANNED_JOBS_SHA256 = (
    "5adf682ee48a868acbe01d9e0b9e33133db26089119396b3539b4e9cb8af5bb6"
)
RANK_POLICY_SHA256 = (
    "1700ada1985e622c9b6def95960b313f12cbb95fd290aa608b09eb44f2cad7ec"
)
RANK_POLICY_SIZE = 46396

LADDER_PATH = "scripts/research/harness_synthetic_edge_calibration_v2_inherited_ladder.py"
PRODUCTION_PATH = "scripts/research/harness_synthetic_edge_calibration_v2_production.py"
V2_POLICY_PATH = "scripts/research/harness_synthetic_edge_calibration_v2_rank_policy.py"

FREEZE_ARTIFACT_PATH = (
    "docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V2_EXECUTION_FREEZE.json"
)
FREEZE_DOCUMENT_PATH = (
    "docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V2_EXECUTION_FREEZE.md"
)

EXPECTED_WORLD_RECORDS_SHA256 = (
    "d372eb00d4f6df9b4f8a2b0dcb22b051d95787ddeb8494a3c0efc31561e39821"
)
EXPECTED_VISIBILITY_SHA256 = (
    "9be8dceb07d8fc43b01ef8630d4ad9f52e7401fd6f095b3c7a5bf364701c8b65"
)
EXPECTED_RESULT_SHA256 = (
    "761cc9afc59265bfb94afecbd293082c274abf3affce3d9693f463442326c1e0"
)

WORLD_RECORDS_PATH = (
    "docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V2_RANK_DEGENERACY_POLICY_WORLD_RECORDS.json"
)
VISIBILITY_PATH = (
    "docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V2_RANK_DEGENERACY_POLICY_VISIBILITY.json"
)
RESULT_PATH = (
    "docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V2_RANK_DEGENERACY_POLICY_RESULT.json"
)
ARM_PATH = (
    "docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V2_RANK_DEGENERACY_POLICY_PRODUCTION_ARM.json"
)
ARM_MD_PATH = (
    "docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V2_RANK_DEGENERACY_POLICY_PRODUCTION_ARM.md"
)
RESERVATION_PATH = (
    "docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V2_RANK_DEGENERACY_POLICY_RESERVATION.json"
)

IMPLEMENTATION_PATHS = (LADDER_PATH, PRODUCTION_PATH, V2_POLICY_PATH)

FREEZE_ALLOWED_CHANGED_PATHS = {
    FREEZE_ARTIFACT_PATH,
    FREEZE_DOCUMENT_PATH,
    "tests/research/test_harness_synthetic_edge_calibration_v2_control_calibration_execution_freeze.py",
    "docs/DOCUMENTATION_INDEX.md",
    "docs/RESEARCH_LEDGER.md",
    ARM_PATH,
    ARM_MD_PATH,
    WORLD_RECORDS_PATH,
    RESULT_PATH,
    RESERVATION_PATH,
}

AUTHORITY_MUST_BE_UNCHANGED = IMPLEMENTATION_PATHS


def _git(*args: str) -> str:
    return subprocess.check_output(["git", "-C", str(REPO), *args], text=True).strip()


def _freeze_commit() -> str:
    path = _git(
        "rev-list", "--ancestry-path", "--reverse", f"{IMPLEMENTATION_HEAD}..HEAD"
    ).splitlines()
    assert path, "current HEAD is not a descendant of IMPLEMENTATION_HEAD"
    freeze = path[0]
    assert _git("rev-parse", f"{freeze}^") == IMPLEMENTATION_HEAD
    return freeze


def _blob_sha256(commit: str, path: str) -> str:
    raw = subprocess.check_output(
        ["git", "-C", str(REPO), "cat-file", "-p", f"{commit}:{path}"]
    )
    return hashlib.sha256(raw).hexdigest()


def _freeze_artifact_at(commit: str) -> dict:
    raw = subprocess.check_output(
        ["git", "-C", str(REPO), "cat-file", "-p", f"{commit}:{FREEZE_ARTIFACT_PATH}"]
    )
    return json.loads(raw)


def test_freeze_parent_is_approved_implementation():
    freeze_commit = _freeze_commit()
    assert _git("rev-parse", f"{freeze_commit}^") == IMPLEMENTATION_HEAD
    assert _git("rev-parse", f"{IMPLEMENTATION_HEAD}^{{tree}}") == IMPLEMENTATION_TREE


def test_canonical_plan_and_rank_policy_identities():
    from scripts.research.harness_synthetic_edge_calibration_v2_production import (
        canonical_v2_plan,
        canonical_v2_world_count,
        canonical_v2_production_jobs,
    )
    from scripts.research.harness_synthetic_edge_calibration_v1_production import (
        planned_jobs_sha256,
        planned_production_jobs,
    )

    freeze_commit = _freeze_commit()
    freeze = _freeze_artifact_at(freeze_commit)
    plan = canonical_v2_plan(repo_root=REPO, commit=freeze_commit)
    impl_plan = canonical_v2_plan(repo_root=REPO, commit=IMPLEMENTATION_HEAD)
    assert plan["sha256"] == CANONICAL_V2_PLAN_SHA256
    assert impl_plan["sha256"] == CANONICAL_V2_PLAN_SHA256
    assert freeze["canonical_v2_plan"]["sha256"] == CANONICAL_V2_PLAN_SHA256
    assert freeze["canonical_v2_plan"]["world_count"] == CANONICAL_WORLD_COUNT
    assert canonical_v2_world_count() == CANONICAL_WORLD_COUNT
    jobs = canonical_v2_production_jobs()
    assert jobs == planned_production_jobs()
    assert len(jobs) == 3200
    assert jobs[0] == ("NULL", 5000, 0)
    assert jobs[-1] == ("SMALL", 10000, 399)
    assert planned_jobs_sha256(jobs) == V1_PLANNED_JOBS_SHA256
    assert _blob_sha256(IMPLEMENTATION_HEAD, V2_POLICY_PATH) == RANK_POLICY_SHA256
    assert int(_git("cat-file", "-s", f"{IMPLEMENTATION_HEAD}:{V2_POLICY_PATH}")) == RANK_POLICY_SIZE


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


def test_freeze_does_not_carry_arm_or_protected_artifacts():
    from scripts.research import harness_synthetic_edge_calibration_v2_production as v2p

    freeze_commit = _freeze_commit()
    assert v2p._commit_blob(REPO, freeze_commit, ARM_PATH) is None
    assert v2p._v2_protected_artifacts_present_at(REPO, freeze_commit) is False


def test_freeze_production_state_not_armed():
    freeze = _freeze_artifact_at(_freeze_commit())
    state = freeze["production_state"]
    assert state["production_armed"] is False
    assert state["production_executed"] is False
    assert state["result_minted"] is False
    assert state["world_records_created"] is False
    assert state["authority_consumed"] is False
    assert state["arm_created"] is False
    assert state["execution_authorized"] is False
    assert state["canonical_3200_run_started"] is False
    assert freeze["visibility_limitation"]["status"] == "UNRESOLVED_FAIL_CLOSED"


def test_freeze_authenticates():
    from scripts.research import harness_synthetic_edge_calibration_v2_production as v2p

    freeze_commit = _freeze_commit()
    authenticated = v2p._authenticate_v2_execution_freeze(REPO, freeze_commit)
    assert authenticated is not None
    assert authenticated["reviewed_implementation"]["head"] == IMPLEMENTATION_HEAD
    assert authenticated["canonical_v2_plan"]["sha256"] == CANONICAL_V2_PLAN_SHA256


def test_historical_arm_still_verifies_old_plan():
    from scripts.research import harness_synthetic_edge_calibration_v2_production as v2p

    bound = v2p.verify_historical_v2_execution_authority(REPO, HISTORICAL_ARM_HEAD)
    assert bound["arm_commit"] == HISTORICAL_ARM_HEAD
    assert bound["freeze_parent_head"] == HISTORICAL_FREEZE_HEAD
    assert bound["canonical_v2_plan_sha256"] == HISTORICAL_PLAN_SHA256
    assert bound["run_identity"] == HISTORICAL_RUN_IDENTITY
    assert bound["canonical_v2_plan_sha256"] != CANONICAL_V2_PLAN_SHA256


def test_old_canonical_evidence_blobs_unchanged():
    assert _blob_sha256(IMPLEMENTATION_HEAD, WORLD_RECORDS_PATH) == EXPECTED_WORLD_RECORDS_SHA256
    assert _blob_sha256(IMPLEMENTATION_HEAD, VISIBILITY_PATH) == EXPECTED_VISIBILITY_SHA256
    assert _blob_sha256(IMPLEMENTATION_HEAD, RESULT_PATH) == EXPECTED_RESULT_SHA256


def test_future_arm_can_bind_this_freeze_without_runtime_edit(tmp_path):
    import subprocess as sp

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
    assert payload["canonical_v2_plan_sha256"] == CANONICAL_V2_PLAN_SHA256
    (repo / v2p.CANONICAL_V2_ARM_PATH).write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    sp.run(["git", "-C", str(repo), "add", "-A"], check=True)
    sp.run(
        ["git", "-C", str(repo), "commit", "-q", "-m", "disposable arm probe (not pushed)"],
        check=True,
    )
    assert v2p.v2_production_arm_authorized(repo_root=repo) is True
