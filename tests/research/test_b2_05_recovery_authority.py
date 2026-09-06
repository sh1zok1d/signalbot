"""Pin the committed B2-05 recovery authority. No market data, no artifact I/O."""
from __future__ import annotations

import inspect
import json
import subprocess
from pathlib import Path

from scripts.research.lib.batch02_contracts import recover_claimed_batch02_artifact
from scripts.research.lib.batch02_evidence_retention import (
    HISTORICAL_ARTIFACT_BINDING_OPERATOR_ADJUDICATED,
    build_recovery_authority_payload,
    canonical_json_bytes,
    recover_claimed_batch02_artifact as recover_impl,
    recovery_authority_relpath,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
EXECUTION_SHA = "669ae93c6a5c1d102a46fd129f04292f1beff978"
AUTHORITY_RELPATH = recovery_authority_relpath("B2-05_FLOW_ABSORPTION", EXECUTION_SHA)


def test_committed_b2_05_recovery_authority_is_operator_adjudicated():
    path = REPO_ROOT / AUTHORITY_RELPATH
    assert path.is_file()
    assert not path.is_symlink()
    raw = path.read_bytes()
    payload = json.loads(raw.decode("utf-8"))
    rebuilt = build_recovery_authority_payload(
        hypothesis_id=str(payload["hypothesis_id"]),
        stage=str(payload["stage"]),
        dataset_id=str(payload["dataset_id"]),
        snapshot_id=str(payload["snapshot_id"]),
        execution_code_sha=str(payload["execution_code_sha"]),
        execution_code_tree=str(payload["execution_code_tree"]),
        evidence_ref=str(payload["evidence_ref"]),
        reservation_commit_sha=str(payload["reservation_commit_sha"]),
        claim_commit_sha=str(payload["claim_commit_sha"]),
        artifact_sha256=str(payload["artifact_sha256"]),
        artifact_size_bytes=payload["artifact_size_bytes"],
        run_identity_sha256=str(payload["run_identity_sha256"]),
        canonical_artifact_path=str(payload["canonical_artifact_path"]),
        historical_artifact_binding=str(payload["historical_artifact_binding"]),
    )
    assert canonical_json_bytes(payload) == canonical_json_bytes(rebuilt)
    assert (
        payload["historical_artifact_binding"]
        == HISTORICAL_ARTIFACT_BINDING_OPERATOR_ADJUDICATED
    )
    assert "historical_execution_persistence_proven" not in payload
    assert payload["artifact_sha256"] == (
        "530342759e70a135915ef82382b4b97bd939620ce02925524b745ccf6cc9a57c"
    )
    assert payload["artifact_size_bytes"] == 280017092
    assert payload["execution_code_sha"] == EXECUTION_SHA
    assert payload["execution_code_sha"] != payload["claim_commit_sha"]
    tracked = subprocess.run(  # noqa: S603 - fixed argv, no shell, test-only
        ["git", "ls-tree", "-r", "--full-tree", "HEAD", "--", AUTHORITY_RELPATH],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert tracked.startswith("100644 blob ")
    assert tracked.endswith(f"\t{AUTHORITY_RELPATH}")


def test_recover_api_still_rejects_caller_artifact_authority():
    allowed = {
        "repo_root",
        "recovery_code_sha",
        "recovery_code_tree",
        "authority_relpath",
        "test_bare_remote",
    }
    assert set(inspect.signature(recover_claimed_batch02_artifact).parameters) == allowed
    assert set(inspect.signature(recover_impl).parameters) == allowed
