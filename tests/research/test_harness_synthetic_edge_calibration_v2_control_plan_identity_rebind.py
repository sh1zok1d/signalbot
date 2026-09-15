"""Identity-only rebind of FROZEN_CANONICAL_V2_PLAN_SHA256.

These tests must not run the 3200-world grid, mint RESULT/WORLD_RECORDS,
create a production freeze/ARM/reservation, or change scientific computation.
They prove the production authority constant now matches the live plan SHA
of the already-reviewed confirmatory-power repair, that the 3200-world job
set is unchanged, and that a disposable freeze whose parent is this
implementation HEAD can authenticate.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from scripts.research import harness_synthetic_edge_calibration_v1_production as prod
from scripts.research import harness_synthetic_edge_calibration_v2_production as v2p
from tests.research.test_harness_synthetic_edge_calibration_v2_production import (
    _git,
    _v2_commit_freeze_tree,
)

REPO = Path(__file__).resolve().parents[2]

REPAIRED_IMPLEMENTATION_HEAD = "dfd05b6b45eee12660ea4c5914fc781bd327104b"
OLD_AUTHORIZED_IMPLEMENTATION_HEAD = "baf9f23045f4c19418eaaf3a9a7a1b69e21aff98"

EXPECTED_NEW_PLAN_SHA256 = (
    "b0ed15534ef0cf45f1232baa0d7c1881fb3a8aaa086477d67a5ab7e9198c677f"
)
EXPECTED_OLD_PLAN_SHA256 = (
    "7fa12fd3b939cd210a69da37659fd1013a1dba43aca4c06abb6f5a6442a33800"
)
EXPECTED_JOBS_SHA256 = (
    "5adf682ee48a868acbe01d9e0b9e33133db26089119396b3539b4e9cb8af5bb6"
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
EXPECTED_RANK_POLICY_SHA256 = (
    "1700ada1985e622c9b6def95960b313f12cbb95fd290aa608b09eb44f2cad7ec"
)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def test_frozen_plan_authority_matches_repaired_live_plan():
    live = v2p.canonical_v2_plan(repo_root=REPO, commit="HEAD")
    repaired = v2p.canonical_v2_plan(
        repo_root=REPO, commit=REPAIRED_IMPLEMENTATION_HEAD
    )
    old = v2p.canonical_v2_plan(
        repo_root=REPO, commit=OLD_AUTHORIZED_IMPLEMENTATION_HEAD
    )
    assert v2p.FROZEN_CANONICAL_V2_PLAN_SHA256 == EXPECTED_NEW_PLAN_SHA256
    assert live["sha256"] == EXPECTED_NEW_PLAN_SHA256
    assert live["sha256"] == v2p.FROZEN_CANONICAL_V2_PLAN_SHA256
    assert repaired["sha256"] == EXPECTED_NEW_PLAN_SHA256
    assert old["sha256"] == EXPECTED_OLD_PLAN_SHA256
    assert live["sha256"] != EXPECTED_OLD_PLAN_SHA256


def test_world_job_set_unchanged_from_old_authorized_plan():
    live = v2p.canonical_v2_plan(repo_root=REPO, commit="HEAD")
    old = v2p.canonical_v2_plan(
        repo_root=REPO, commit=OLD_AUTHORIZED_IMPLEMENTATION_HEAD
    )
    jobs = v2p.canonical_v2_production_jobs()
    assert jobs == prod.planned_production_jobs()
    assert len(jobs) == 3200
    assert v2p.canonical_v2_world_count() == 3200
    assert v2p.FROZEN_CANONICAL_WORLD_COUNT == 3200
    assert jobs[0] == ("NULL", 5000, 0)
    assert jobs[-1] == ("SMALL", 10000, 399)
    assert prod.planned_jobs_sha256(jobs) == EXPECTED_JOBS_SHA256
    assert live["payload"]["v1_planned_jobs_sha256"] == EXPECTED_JOBS_SHA256
    assert old["payload"]["v1_planned_jobs_sha256"] == EXPECTED_JOBS_SHA256
    assert live["payload"]["v1_planned_worlds"] == old["payload"]["v1_planned_worlds"] == 3200
    assert live["payload"]["v1_frozen_grid"] == old["payload"]["v1_frozen_grid"]
    assert live["payload"]["v2_policy_path"] == old["payload"]["v2_policy_path"]
    assert live["payload"]["schema"] == old["payload"]["schema"]
    assert live["payload"]["schema_version"] == old["payload"]["schema_version"]
    # Plan SHA differs only by repaired rank-policy identity bytes.
    assert live["payload"]["v2_policy_sha256"] == EXPECTED_RANK_POLICY_SHA256
    assert live["payload"]["v2_policy_sha256"] != old["payload"]["v2_policy_sha256"]
    assert live["payload"]["v2_policy_size"] != old["payload"]["v2_policy_size"]


def test_rank_policy_bytes_unchanged_from_reviewed_repair():
    live = v2p._commit_blob(REPO, "HEAD", v2p.V2_POLICY_REL)
    repaired = v2p._commit_blob(REPO, REPAIRED_IMPLEMENTATION_HEAD, v2p.V2_POLICY_REL)
    ladder_live = v2p._commit_blob(REPO, "HEAD", v2p.V2_INHERITED_LADDER_REL)
    ladder_repaired = v2p._commit_blob(
        REPO, REPAIRED_IMPLEMENTATION_HEAD, v2p.V2_INHERITED_LADDER_REL
    )
    assert live == repaired
    assert ladder_live == ladder_repaired
    assert _sha(live) == EXPECTED_RANK_POLICY_SHA256
    assert len(live) == 46396


def test_old_canonical_evidence_bytes_unchanged():
    world_records = (REPO / v2p.CANONICAL_V2_WORLD_RECORDS_PATH).read_bytes()
    visibility = (
        REPO
        / "docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V2_RANK_DEGENERACY_POLICY_VISIBILITY.json"
    ).read_bytes()
    result = (REPO / v2p.CANONICAL_V2_RESULT_PATH).read_bytes()
    assert _sha(world_records) == EXPECTED_WORLD_RECORDS_SHA256
    assert _sha(visibility) == EXPECTED_VISIBILITY_SHA256
    assert _sha(result) == EXPECTED_RESULT_SHA256


def test_disposable_freeze_authenticates_against_rebound_plan(tmp_path):
    repo = _v2_commit_freeze_tree(tmp_path)
    freeze_commit = _git(repo, "rev-parse", "HEAD")
    implementation_head = _git(repo, "rev-parse", f"{freeze_commit}^")
    authenticated = v2p._authenticate_v2_execution_freeze(repo, freeze_commit)
    assert authenticated is not None
    live_plan = v2p.canonical_v2_plan(repo_root=repo, commit=freeze_commit)
    impl_plan = v2p.canonical_v2_plan(repo_root=repo, commit=implementation_head)
    assert live_plan["sha256"] == EXPECTED_NEW_PLAN_SHA256
    assert impl_plan["sha256"] == EXPECTED_NEW_PLAN_SHA256
    assert authenticated["canonical_v2_plan"]["sha256"] == EXPECTED_NEW_PLAN_SHA256
    assert authenticated["canonical_v2_plan"]["sha256"] == v2p.FROZEN_CANONICAL_V2_PLAN_SHA256
    # Immediate parent is the cloned implementation HEAD, not a production freeze.
    assert implementation_head == _git(repo, "rev-parse", f"{freeze_commit}^")
    assert v2p._commit_blob(repo, freeze_commit, v2p.CANONICAL_V2_ARM_PATH) is None
    assert v2p._v2_protected_artifacts_present_at(repo, freeze_commit) is False
    # This proof must not create a production ARM or reservation.
    assert v2p.v2_production_arm_authorized(repo_root=repo) is False
