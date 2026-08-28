from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from scripts.research.lib.research_harness import (
    ArtifactExistsError,
    DatasetIdentityContract,
    DatasetIdentityError,
    LookaheadError,
    OutcomeAccessPolicy,
    OutcomeBoundaryError,
    SupportMismatchError,
    assert_no_lookahead,
    authorize_dataset_access,
    build_run_identity,
    fail_closed_gate_conjunction,
    paired_same_support_delta,
    sha256_file,
    weighted_same_support_delta,
    write_json_new,
)


IDENTITY = DatasetIdentityContract(
    dataset_id="CORE_BTC_BINANCE_V0",
    snapshot_id="snapshot-abc",
)
POLICY = OutcomeAccessPolicy(
    stage="development",
    start_inclusive_ms=1_000,
    end_exclusive_ms=10_000,
    allowed_years=(2020, 2021),
)


def _authorized(tmp_path: Path):
    repo_manifest = tmp_path / "repo.yaml"
    repo_manifest.write_text(
        yaml.safe_dump(
            {
                "dataset_id": IDENTITY.dataset_id,
                "snapshot_id": IDENTITY.snapshot_id,
                "status": "ACCEPTED_FOR_DISCOVERY",
                "research_authorized": True,
                "confirmatory_authorized": False,
            }
        ),
        encoding="utf-8",
    )
    dataset_root = tmp_path / "dataset"
    (dataset_root / "reports").mkdir(parents=True)
    (dataset_root / "reports" / "snapshot_manifest.json").write_text(
        json.dumps(
            {
                "dataset_id": IDENTITY.dataset_id,
                "snapshot_id": IDENTITY.snapshot_id,
            }
        ),
        encoding="utf-8",
    )
    monthly = dataset_root / "canonical" / "1m" / "monthly"
    monthly.mkdir(parents=True)
    return (
        authorize_dataset_access(
            repo_manifest_path=repo_manifest,
            dataset_root=dataset_root,
            identity=IDENTITY,
            policy=POLICY,
        ),
        monthly,
    )


def test_dataset_identity_is_required_before_partition_access(tmp_path: Path):
    dataset_root = tmp_path / "dataset"
    (dataset_root / "canonical" / "1m" / "monthly").mkdir(parents=True)
    with pytest.raises(DatasetIdentityError, match="repository dataset manifest"):
        authorize_dataset_access(
            repo_manifest_path=tmp_path / "missing.yaml",
            dataset_root=dataset_root,
            identity=IDENTITY,
            policy=POLICY,
        )


def test_wrong_runtime_snapshot_fails_closed(tmp_path: Path):
    repo_manifest = tmp_path / "repo.yaml"
    repo_manifest.write_text(
        yaml.safe_dump(
            {
                "dataset_id": IDENTITY.dataset_id,
                "snapshot_id": IDENTITY.snapshot_id,
                "status": "ACCEPTED_FOR_DISCOVERY",
                "research_authorized": True,
                "confirmatory_authorized": False,
            }
        ),
        encoding="utf-8",
    )
    dataset_root = tmp_path / "dataset"
    (dataset_root / "reports").mkdir(parents=True)
    (dataset_root / "reports" / "snapshot_manifest.json").write_text(
        json.dumps({"snapshot_id": "wrong"}),
        encoding="utf-8",
    )
    with pytest.raises(DatasetIdentityError, match="runtime snapshot_id"):
        authorize_dataset_access(
            repo_manifest_path=repo_manifest,
            dataset_root=dataset_root,
            identity=IDENTITY,
            policy=POLICY,
        )


def test_forbidden_year_partition_is_not_exposed(tmp_path: Path):
    authorized, monthly = _authorized(tmp_path)
    (monthly / "2020-01.parquet").touch()
    (monthly / "2021-12.parquet").touch()
    (monthly / "2025-01.parquet").touch()
    assert [p.name for p in authorized.list_monthly_partitions()] == [
        "2020-01.parquet",
        "2021-12.parquet",
    ]


def test_outcome_boundary_rejects_holdout_reach(tmp_path: Path):
    authorized, monthly = _authorized(tmp_path)
    (monthly / "2020-01.parquet").touch()
    authorized.assert_outcome_window(8_999, 1_000)
    with pytest.raises(OutcomeBoundaryError):
        authorized.assert_outcome_window(9_000, 1_000)


def test_no_lookahead_accepts_equality_and_rejects_future_availability():
    assert_no_lookahead([100, 200], [100, 199])
    with pytest.raises(LookaheadError, match="lookahead"):
        assert_no_lookahead([100, 200], [100, 201])


def test_paired_support_never_silently_intersects():
    with pytest.raises(SupportMismatchError, match="supports differ"):
        paired_same_support_delta({"a": 1.0, "b": 9.0}, {"a": 0.0})
    out = paired_same_support_delta(
        {"a": 1.0, "b": 9.0},
        {"a": 0.0},
        support_ids=["a"],
    )
    assert out["support_n"] == 1
    assert out["delta"] == pytest.approx(1.0)


def test_weighted_same_support_blocks_full_candidate_vs_overlap_control_forgery():
    candidate = {"overlap": 1.0, "candidate_only": 100.0}
    reference = {"overlap": 0.25}
    weights = {"overlap": 2.0}

    with pytest.raises(SupportMismatchError, match="supports differ"):
        weighted_same_support_delta(candidate, reference, weights)

    out = weighted_same_support_delta(
        candidate,
        reference,
        weights,
        support_keys=["overlap"],
    )
    assert out["candidate_support_mean"] == pytest.approx(1.0)
    assert out["reference_support_mean"] == pytest.approx(0.25)
    assert out["delta"] == pytest.approx(0.75)


def test_weighted_support_requires_same_finite_positive_weights():
    with pytest.raises(SupportMismatchError, match="must be > 0"):
        weighted_same_support_delta(
            {"a": 1.0},
            {"a": 0.0},
            {"a": 0.0},
        )


def test_gate_conjunction_is_literal_true_and_fail_closed():
    names = ["primary", "matched", "structural"]
    assert fail_closed_gate_conjunction(
        {"primary": True, "matched": True, "structural": True},
        names,
    )
    assert not fail_closed_gate_conjunction(
        {"primary": True, "matched": True},
        names,
    )
    assert not fail_closed_gate_conjunction(
        {"primary": True, "matched": None, "structural": True},
        names,
    )
    assert not fail_closed_gate_conjunction(
        {"primary": True, "matched": 1, "structural": True},
        names,
    )
    assert not fail_closed_gate_conjunction({}, [])


def test_provenance_and_result_artifact_are_immutable(tmp_path: Path):
    authorized, monthly = _authorized(tmp_path)
    (monthly / "2020-01.parquet").touch()
    identity = build_run_identity(
        hypothesis_id="B02_TEST",
        stage="development",
        code_sha="abc123",
        authorized_dataset=authorized,
        command=["python", "-m", "scripts.research.experiments.b02_test"],
        seeds={"bootstrap": 7, "matched": 3},
    )
    assert identity["dataset_id"] == IDENTITY.dataset_id
    assert identity["snapshot_id"] == IDENTITY.snapshot_id
    assert identity["seeds"] == {"bootstrap": 7, "matched": 3}

    path = tmp_path / "result.json"
    digest = write_json_new(path, {"identity": identity, "promotion": False})
    assert digest == sha256_file(path)

    with pytest.raises(ArtifactExistsError, match="refusing to overwrite"):
        write_json_new(path, {"identity": identity, "promotion": True})
