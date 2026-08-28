from __future__ import annotations

import json
import subprocess
from pathlib import Path

import numpy as np
import pytest
import yaml

from scripts.research.lib.research_harness import (
    ArtifactExistsError,
    AuthorizedDataset,
    CodeIdentityError,
    DISCOVERY_END_EXCLUSIVE_MS,
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
    verify_git_freeze,
    weighted_same_support_delta,
    write_json_new,
)


IDENTITY = DatasetIdentityContract(
    dataset_id="CORE_BTC_BINANCE_V0",
    snapshot_id="snapshot-abc",
)
START_2020_MS = 1_577_836_800_000
END_2022_MS = 1_640_995_200_000

POLICY = OutcomeAccessPolicy(
    stage="development",
    start_inclusive_ms=START_2020_MS,
    end_exclusive_ms=END_2022_MS,
    allowed_years=(2020, 2021),
)


def _authorized(
    tmp_path: Path,
    partition_contents: dict[str, bytes] | None = None,
):
    tmp_path.mkdir(parents=True, exist_ok=True)
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
    monthly = dataset_root / "canonical" / "1m" / "monthly"
    monthly.mkdir(parents=True)

    output_checksums: dict[str, str] = {}
    for name, body in (partition_contents or {}).items():
        path = monthly / name
        path.write_bytes(body)
        relative = path.relative_to(dataset_root).as_posix()
        output_checksums[relative] = sha256_file(path)

    (dataset_root / "reports" / "snapshot_manifest.json").write_text(
        json.dumps(
            {
                "snapshot_id": IDENTITY.snapshot_id,
                "identity_payload": {
                    "dataset_id": IDENTITY.dataset_id,
                    "output_checksums": output_checksums,
                },
            }
        ),
        encoding="utf-8",
    )
    return (
        authorize_dataset_access(
            repo_manifest_path=repo_manifest,
            dataset_root=dataset_root,
            identity=IDENTITY,
            policy=POLICY,
        ),
        monthly,
    )


def test_dataset_contract_cannot_relax_discovery_authorization():
    with pytest.raises(ValueError, match="ACCEPTED_FOR_DISCOVERY"):
        DatasetIdentityContract(
            dataset_id="CORE_BTC_BINANCE_V0",
            snapshot_id="snapshot-abc",
            required_status="MATERIALIZED_UNVERIFIED",
        )
    with pytest.raises(ValueError, match="research_authorized"):
        DatasetIdentityContract(
            dataset_id="CORE_BTC_BINANCE_V0",
            snapshot_id="snapshot-abc",
            research_authorized=False,
        )
    with pytest.raises(ValueError, match="confirmatory_authorized"):
        DatasetIdentityContract(
            dataset_id="CORE_BTC_BINANCE_V0",
            snapshot_id="snapshot-abc",
            confirmatory_authorized=True,
        )


def test_policy_is_development_only_and_cannot_reach_2025():
    with pytest.raises(ValueError, match="only 'development'"):
        OutcomeAccessPolicy(
            stage="validation",
            start_inclusive_ms=START_2020_MS,
            end_exclusive_ms=END_2022_MS,
            allowed_years=(2020, 2021),
        )

    with pytest.raises(ValueError, match="2025 validation pool"):
        OutcomeAccessPolicy(
            stage="development",
            start_inclusive_ms=START_2020_MS,
            end_exclusive_ms=DISCOVERY_END_EXCLUSIVE_MS + 1,
            allowed_years=(2020, 2021),
        )


def test_policy_rejects_allowed_year_outside_frozen_window():
    with pytest.raises(ValueError, match="outside frozen time window"):
        OutcomeAccessPolicy(
            stage="development",
            start_inclusive_ms=START_2020_MS,
            end_exclusive_ms=END_2022_MS,
            allowed_years=(2020, 2025),
        )


def test_policy_freezes_allowed_years_and_rejects_bool_aliases():
    years = [2020, 2021]
    policy = OutcomeAccessPolicy(
        stage="development",
        start_inclusive_ms=START_2020_MS,
        end_exclusive_ms=END_2022_MS,
        allowed_years=years,
    )
    years.append(2025)
    assert policy.allowed_years == (2020, 2021)

    with pytest.raises(ValueError, match="allowed_years must contain integers"):
        OutcomeAccessPolicy(
            stage="development",
            start_inclusive_ms=START_2020_MS,
            end_exclusive_ms=END_2022_MS,
            allowed_years=(2020, True),
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


def test_invalid_repository_manifest_yaml_fails_closed(tmp_path: Path):
    repo_manifest = tmp_path / "repo.yaml"
    repo_manifest.write_text("dataset_id: [unterminated\n", encoding="utf-8")
    dataset_root = tmp_path / "dataset"

    with pytest.raises(DatasetIdentityError, match="invalid repository dataset manifest YAML"):
        authorize_dataset_access(
            repo_manifest_path=repo_manifest,
            dataset_root=dataset_root,
            identity=IDENTITY,
            policy=POLICY,
        )


def test_authorized_dataset_cannot_be_forged_directly(tmp_path: Path):
    with pytest.raises(DatasetIdentityError, match="authorize_dataset_access"):
        AuthorizedDataset(
            dataset_root=tmp_path,
            identity=IDENTITY,
            policy=POLICY,
            repo_manifest_path=tmp_path / "repo.yaml",
            runtime_snapshot_path=tmp_path / "snapshot.json",
            output_checksums=(),
        )


def test_runtime_dataset_id_is_required_from_realistic_identity_payload(tmp_path: Path):
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

    snapshot_path = dataset_root / "reports" / "snapshot_manifest.json"
    snapshot_path.write_text(
        json.dumps(
            {
                "snapshot_id": IDENTITY.snapshot_id,
                "identity_payload": {
                    "dataset_id": IDENTITY.dataset_id,
                    "output_checksums": {},
                },
            }
        ),
        encoding="utf-8",
    )
    authorize_dataset_access(
        repo_manifest_path=repo_manifest,
        dataset_root=dataset_root,
        identity=IDENTITY,
        policy=POLICY,
    )

    snapshot_path.write_text(
        json.dumps({
            "snapshot_id": IDENTITY.snapshot_id,
            "identity_payload": {"output_checksums": {}},
        }),
        encoding="utf-8",
    )
    with pytest.raises(DatasetIdentityError, match="runtime dataset_id"):
        authorize_dataset_access(
            repo_manifest_path=repo_manifest,
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
    authorized, monthly = _authorized(
        tmp_path,
        {
            "2020-01.parquet": b"allowed-2020",
            "2021-12.parquet": b"allowed-2021",
            "2025-01.parquet": b"forbidden-2025",
        },
    )
    assert [p.name for p in authorized.list_monthly_partitions()] == [
        "2020-01.parquet",
        "2021-12.parquet",
    ]


def test_selected_partition_requires_frozen_checksum_and_matching_bytes(tmp_path: Path):
    authorized, monthly = _authorized(
        tmp_path,
        {"2020-01.parquet": b"frozen-bytes"},
    )
    assert [p.name for p in authorized.list_monthly_partitions()] == [
        "2020-01.parquet"
    ]

    (monthly / "2020-01.parquet").write_bytes(b"tampered-bytes")
    with pytest.raises(DatasetIdentityError, match="checksum mismatch"):
        authorized.list_monthly_partitions()

    missing_authorized, missing_monthly = _authorized(tmp_path / "missing")
    (missing_monthly / "2020-01.parquet").write_bytes(b"unregistered")
    with pytest.raises(DatasetIdentityError, match="missing frozen checksum"):
        missing_authorized.list_monthly_partitions()


def test_outcome_boundary_rejects_holdout_reach(tmp_path: Path):
    authorized, _monthly = _authorized(tmp_path)
    authorized.assert_outcome_window(END_2022_MS - 1_001, 1_000)
    with pytest.raises(OutcomeBoundaryError):
        authorized.assert_outcome_window(END_2022_MS - 1_000, 1_000)


def test_no_lookahead_accepts_numpy_scalar_and_rejects_future_availability():
    assert_no_lookahead(np.int64(100), np.int64(100))
    assert_no_lookahead([100, 200], [100, 199])
    with pytest.raises(LookaheadError, match="lookahead"):
        assert_no_lookahead([100, 200], [100, 201])


def _init_clean_git_repo(root: Path) -> str:
    root.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init"], cwd=root, check=True, capture_output=True)
    (root / "tracked.txt").write_text("frozen\n", encoding="utf-8")
    subprocess.run(["git", "add", "tracked.txt"], cwd=root, check=True)
    subprocess.run(
        [
            "git", "-c", "user.name=Harness Test",
            "-c", "user.email=harness@example.invalid",
            "commit", "-m", "freeze",
        ],
        cwd=root,
        check=True,
        capture_output=True,
    )
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def test_git_freeze_requires_exact_clean_head(tmp_path: Path):
    repo = tmp_path / "repo"
    sha = _init_clean_git_repo(repo)

    proof = verify_git_freeze(repo, sha)
    assert proof.code_sha == sha

    with pytest.raises(CodeIdentityError, match="40-hex"):
        verify_git_freeze(repo, sha[:12])

    with pytest.raises(CodeIdentityError, match="HEAD mismatch"):
        verify_git_freeze(repo, "0" * 40)

    (repo / "tracked.txt").write_text("dirty\n", encoding="utf-8")
    with pytest.raises(CodeIdentityError, match="not clean"):
        verify_git_freeze(repo, sha)


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


def test_run_identity_rejects_lookalike_proof_objects(tmp_path: Path):
    authorized, _monthly = _authorized(tmp_path)
    repo = tmp_path / "code"
    code_sha = _init_clean_git_repo(repo)
    code_freeze = verify_git_freeze(repo, code_sha)

    class FakeCodeFreeze:
        pass

    fake_code_freeze = FakeCodeFreeze()
    fake_code_freeze.code_sha = code_sha

    class FakeAuthorizedDataset:
        pass

    fake_authorized_dataset = FakeAuthorizedDataset()
    fake_authorized_dataset.policy = authorized.policy
    fake_authorized_dataset.identity = authorized.identity

    with pytest.raises(CodeIdentityError, match="verify_git_freeze proof"):
        build_run_identity(
            hypothesis_id="B02_TEST",
            stage="development",
            code_freeze=fake_code_freeze,
            authorized_dataset=authorized,
            command=["python", "-m", "fake"],
        )

    with pytest.raises(DatasetIdentityError, match="authorize_dataset_access proof"):
        build_run_identity(
            hypothesis_id="B02_TEST",
            stage="development",
            code_freeze=code_freeze,
            authorized_dataset=fake_authorized_dataset,
            command=["python", "-m", "fake"],
        )


def test_provenance_and_result_artifact_are_immutable(tmp_path: Path):
    authorized, _monthly = _authorized(tmp_path)
    repo = tmp_path / "code"
    code_sha = _init_clean_git_repo(repo)
    code_freeze = verify_git_freeze(repo, code_sha)

    identity = build_run_identity(
        hypothesis_id="B02_TEST",
        stage="development",
        code_freeze=code_freeze,
        authorized_dataset=authorized,
        command=["python", "-m", "scripts.research.experiments.b02_test"],
        seeds={"bootstrap": 7, "matched": 3},
    )
    assert identity["dataset_id"] == IDENTITY.dataset_id
    assert identity["snapshot_id"] == IDENTITY.snapshot_id
    assert identity["code_sha"] == code_sha
    assert identity["seeds"] == {"bootstrap": 7, "matched": 3}

    path = tmp_path / "result.json"
    digest = write_json_new(path, {"identity": identity, "promotion": False})
    assert digest == sha256_file(path)

    with pytest.raises(ArtifactExistsError, match="refusing to overwrite"):
        write_json_new(path, {"identity": identity, "promotion": True})


def test_canonical_json_rejects_nonfinite_numbers_before_file_creation(tmp_path: Path):
    path = tmp_path / "bad.json"
    with pytest.raises(ValueError):
        write_json_new(path, {"value": float("nan")})
    assert not path.exists()
