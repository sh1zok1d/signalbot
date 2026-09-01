from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import numpy as np
import pytest
import yaml

from scripts.research.lib.research_harness import (
    ArtifactExistsError,
    AuthorizedDataset,
    AuthorizedPartition,
    CodeIdentityError,
    DISCOVERY_END_EXCLUSIVE_MS,
    DatasetIdentityContract,
    DatasetIdentityError,
    LookaheadError,
    OutcomeAccessPolicy,
    OutcomeBoundaryError,
    PromotionGateContract,
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


SNAPSHOT_ID = "a" * 64
IDENTITY = DatasetIdentityContract(
    dataset_id="CORE_BTC_BINANCE_V0",
    snapshot_id=SNAPSHOT_ID,
)
START_2020_MS = 1_577_836_800_000
END_2022_MS = 1_640_995_200_000
POLICY = OutcomeAccessPolicy(
    stage="development",
    start_inclusive_ms=START_2020_MS,
    end_exclusive_ms=END_2022_MS,
    allowed_years=(2020, 2021),
)
GATE_CONTRACT = PromotionGateContract(
    ("primary", "matched", "structural")
)


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _init_frozen_repo(
    root: Path,
    output_checksums: dict[str, str],
) -> tuple[str, str]:
    root.mkdir(parents=True, exist_ok=True)
    _git(root, "init")

    snapshot_git_path = (
        "docs/research_data/CORE_BTC_BINANCE_V0/SNAPSHOT_SYNTHETIC.json"
    )
    manifest_path = root / "docs" / "manifests" / "CORE_BTC_BINANCE_V0.yaml"
    snapshot_path = root / snapshot_git_path
    manifest_path.parent.mkdir(parents=True)
    snapshot_path.parent.mkdir(parents=True)

    manifest_path.write_text(
        yaml.safe_dump(
            {
                "dataset_id": IDENTITY.dataset_id,
                "snapshot_id": IDENTITY.snapshot_id,
                "status": "ACCEPTED_FOR_DISCOVERY",
                "research_authorized": True,
                "confirmatory_authorized": False,
                "materialization_identity": {
                    "snapshot_manifest_path": snapshot_git_path,
                },
            }
        ),
        encoding="utf-8",
    )
    snapshot_path.write_text(
        json.dumps(
            {
                "snapshot_id": IDENTITY.snapshot_id,
                "identity_payload": {
                    "dataset_id": IDENTITY.dataset_id,
                    "output_checksums": output_checksums,
                },
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    (root / "tracked.txt").write_text("frozen\n", encoding="utf-8")
    _git(root, "add", ".")
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=Harness Test",
            "-c",
            "user.email=harness@example.invalid",
            "commit",
            "-m",
            "freeze",
        ],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    return _git(root, "rev-parse", "HEAD"), snapshot_git_path


def _authorized(
    tmp_path: Path,
    partition_contents: dict[str, bytes] | None = None,
):
    tmp_path.mkdir(parents=True, exist_ok=True)
    dataset_root = tmp_path / "dataset"
    monthly = dataset_root / "canonical" / "1m" / "monthly"
    monthly.mkdir(parents=True)
    (dataset_root / "reports").mkdir(parents=True)

    output_checksums: dict[str, str] = {}
    for name, body in (partition_contents or {"2020-01.parquet": b"allowed"}).items():
        path = monthly / name
        path.write_bytes(body)
        output_checksums[path.relative_to(dataset_root).as_posix()] = sha256_file(path)

    code_repo = tmp_path / "code"
    code_sha, snapshot_git_path = _init_frozen_repo(code_repo, output_checksums)
    code_freeze = verify_git_freeze(code_repo, code_sha)

    runtime_snapshot = dataset_root / "reports" / "snapshot_manifest.json"
    runtime_snapshot.write_text(
        json.dumps(
            {
                "snapshot_id": IDENTITY.snapshot_id,
                "identity_payload": {
                    "dataset_id": IDENTITY.dataset_id,
                    "output_checksums": output_checksums,
                },
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    authorized = authorize_dataset_access(
        code_freeze=code_freeze,
        dataset_root=dataset_root,
        identity=IDENTITY,
        policy=POLICY,
    )
    return {
        "authorized": authorized,
        "dataset_root": dataset_root,
        "monthly": monthly,
        "runtime_snapshot": runtime_snapshot,
        "code_repo": code_repo,
        "code_sha": code_sha,
        "code_freeze": code_freeze,
        "snapshot_git_path": snapshot_git_path,
        "output_checksums": output_checksums,
    }


def test_dataset_contract_cannot_relax_discovery_authorization():
    with pytest.raises(ValueError, match="ACCEPTED_FOR_DISCOVERY"):
        DatasetIdentityContract(
            dataset_id=IDENTITY.dataset_id,
            snapshot_id=IDENTITY.snapshot_id,
            required_status="MATERIALIZED_UNVERIFIED",
        )
    with pytest.raises(ValueError, match="research_authorized"):
        DatasetIdentityContract(
            dataset_id=IDENTITY.dataset_id,
            snapshot_id=IDENTITY.snapshot_id,
            research_authorized=False,
        )
    with pytest.raises(ValueError, match="confirmatory_authorized"):
        DatasetIdentityContract(
            dataset_id=IDENTITY.dataset_id,
            snapshot_id=IDENTITY.snapshot_id,
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


def test_gate_contract_is_immutable_unique_and_nonempty():
    names = ["primary", "matched"]
    contract = PromotionGateContract(names)
    names.append("posthoc")
    assert contract.required_gate_names == ("primary", "matched")
    with pytest.raises(ValueError, match="unique"):
        PromotionGateContract(("primary", "primary"))
    with pytest.raises(ValueError, match="non-empty"):
        PromotionGateContract(())


def test_dataset_authorization_uses_git_frozen_manifest_and_snapshot(tmp_path: Path):
    ctx = _authorized(tmp_path)
    authorized = ctx["authorized"]
    assert authorized.code_sha == ctx["code_sha"]
    assert authorized.repo_manifest_git_path == (
        "docs/manifests/CORE_BTC_BINANCE_V0.yaml"
    )
    assert authorized.frozen_snapshot_git_path == ctx["snapshot_git_path"]
    assert [p.name for p in authorized.list_monthly_partitions()] == [
        "2020-01.parquet"
    ]


def test_runtime_checksum_and_parquet_co_update_cannot_redefine_snapshot(tmp_path: Path):
    ctx = _authorized(tmp_path)
    path = ctx["monthly"] / "2020-01.parquet"
    path.write_bytes(b"substituted")
    rel = path.relative_to(ctx["dataset_root"]).as_posix()
    new_hash = sha256_file(path)
    runtime = json.loads(ctx["runtime_snapshot"].read_text(encoding="utf-8"))
    runtime["identity_payload"]["output_checksums"][rel] = new_hash
    ctx["runtime_snapshot"].write_text(
        json.dumps(runtime, sort_keys=True),
        encoding="utf-8",
    )

    with pytest.raises(DatasetIdentityError, match="Git-frozen snapshot"):
        authorize_dataset_access(
            code_freeze=ctx["code_freeze"],
            dataset_root=ctx["dataset_root"],
            identity=IDENTITY,
            policy=POLICY,
        )
    with pytest.raises(DatasetIdentityError, match="checksum drift"):
        ctx["authorized"].list_monthly_partitions()


def test_runtime_identity_payload_snapshot_id_mismatch_fails(tmp_path: Path):
    ctx = _authorized(tmp_path)
    runtime = json.loads(ctx["runtime_snapshot"].read_text(encoding="utf-8"))
    runtime["identity_payload"]["snapshot_id"] = "b" * 64
    ctx["runtime_snapshot"].write_text(
        json.dumps(runtime, sort_keys=True),
        encoding="utf-8",
    )
    with pytest.raises(DatasetIdentityError, match="identity_payload snapshot_id"):
        authorize_dataset_access(
            code_freeze=ctx["code_freeze"],
            dataset_root=ctx["dataset_root"],
            identity=IDENTITY,
            policy=POLICY,
        )


def test_authorized_proof_exposes_only_selected_partitions_not_dataset_root(tmp_path: Path):
    ctx = _authorized(
        tmp_path,
        {
            "2020-01.parquet": b"allowed-2020",
            "2021-12.parquet": b"allowed-2021",
            "2025-01.parquet": b"forbidden-2025",
        },
    )
    authorized = ctx["authorized"]
    assert not hasattr(authorized, "dataset_root")
    assert [p.name for p in authorized.list_monthly_partitions()] == [
        "2020-01.parquet",
        "2021-12.parquet",
    ]
    assert all("2025-" not in p.relative_path for p in authorized.partitions)


def test_selected_symlink_partition_is_rejected(tmp_path: Path):
    dataset_root = tmp_path / "dataset"
    monthly = dataset_root / "canonical" / "1m" / "monthly"
    monthly.mkdir(parents=True)
    (dataset_root / "reports").mkdir(parents=True)

    target = tmp_path / "target.parquet"
    target.write_bytes(b"target")
    link = monthly / "2020-01.parquet"
    os.symlink(target, link)
    rel = link.relative_to(dataset_root).as_posix()
    output_checksums = {rel: sha256_file(target)}

    code_repo = tmp_path / "code"
    code_sha, _ = _init_frozen_repo(code_repo, output_checksums)
    code_freeze = verify_git_freeze(code_repo, code_sha)
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

    with pytest.raises(DatasetIdentityError, match="must not be a symlink"):
        authorize_dataset_access(
            code_freeze=code_freeze,
            dataset_root=dataset_root,
            identity=IDENTITY,
            policy=POLICY,
        )


def test_outcome_boundary_rejects_holdout_reach(tmp_path: Path):
    ctx = _authorized(tmp_path)
    authorized = ctx["authorized"]
    authorized.assert_outcome_window(END_2022_MS - 1_001, 1_000)
    with pytest.raises(OutcomeBoundaryError):
        authorized.assert_outcome_window(END_2022_MS - 1_000, 1_000)


def test_no_lookahead_accepts_integer_ms_and_rejects_future():
    t0 = 1_600_000_000_000
    assert_no_lookahead(np.int64(t0), np.int64(t0))
    assert_no_lookahead([t0, t0 + 1000], [t0, t0 + 999])
    with pytest.raises(LookaheadError, match="lookahead"):
        assert_no_lookahead([t0, t0 + 1000], [t0, t0 + 1001])


@pytest.mark.parametrize(
    "decision,available",
    [
        (1_600_000_000_000, 1_600_000_000_000.9),
        (1_600_000_000_000, np.float64(1_600_000_000_000)),
        (1_600_000_000_000, "1600000000000"),
        (1_600_000_000_000, b"1600000000000"),
        (1_600_000_000_000, True),
        (1_600_000_000_000, 1_735_689_600),
    ],
)
def test_no_lookahead_rejects_ambiguous_or_wrong_timestamp_types(
    decision,
    available,
):
    with pytest.raises(LookaheadError):
        assert_no_lookahead(decision, available)


def test_no_lookahead_rejects_empty_sequences():
    with pytest.raises(LookaheadError, match="non-empty"):
        assert_no_lookahead([], [])


def test_git_freeze_requires_exact_clean_head(tmp_path: Path):
    code_repo = tmp_path / "code"
    sha, _ = _init_frozen_repo(code_repo, {})
    proof = verify_git_freeze(code_repo, sha)
    assert proof.code_sha == sha
    with pytest.raises(CodeIdentityError, match="40-hex"):
        verify_git_freeze(code_repo, sha[:12])
    with pytest.raises(CodeIdentityError, match="HEAD mismatch"):
        verify_git_freeze(code_repo, "0" * 40)

    (code_repo / "tracked.txt").write_text("dirty\n", encoding="utf-8")
    with pytest.raises(CodeIdentityError, match="not clean"):
        verify_git_freeze(code_repo, sha)


def test_git_freeze_rejects_skip_worktree_hidden_modification(tmp_path: Path):
    code_repo = tmp_path / "code"
    sha, _ = _init_frozen_repo(code_repo, {})
    _git(code_repo, "update-index", "--skip-worktree", "tracked.txt")
    (code_repo / "tracked.txt").write_text("hidden dirty\n", encoding="utf-8")
    assert _git(code_repo, "status", "--porcelain") == ""
    with pytest.raises(CodeIdentityError, match="skip-worktree"):
        verify_git_freeze(code_repo, sha)


def test_git_freeze_rejects_assume_unchanged_hidden_modification(tmp_path: Path):
    code_repo = tmp_path / "code"
    sha, _ = _init_frozen_repo(code_repo, {})
    _git(code_repo, "update-index", "--assume-unchanged", "tracked.txt")
    (code_repo / "tracked.txt").write_text("hidden dirty\n", encoding="utf-8")
    assert _git(code_repo, "status", "--porcelain") == ""
    with pytest.raises(CodeIdentityError, match="assume-unchanged"):
        verify_git_freeze(code_repo, sha)


def test_code_freeze_is_rechecked_before_dataset_authorization(tmp_path: Path):
    ctx = _authorized(tmp_path)
    (ctx["code_repo"] / "tracked.txt").write_text("changed\n", encoding="utf-8")
    with pytest.raises(CodeIdentityError, match="not clean"):
        authorize_dataset_access(
            code_freeze=ctx["code_freeze"],
            dataset_root=ctx["dataset_root"],
            identity=IDENTITY,
            policy=POLICY,
        )


def test_paired_support_requires_exact_support_and_forbids_subset_argument():
    out = paired_same_support_delta(
        {"a": 1.0, "b": 2.0},
        {"a": 0.0, "b": 1.0},
    )
    assert out["support_n"] == 2
    assert out["delta"] == pytest.approx(1.0)

    with pytest.raises(SupportMismatchError, match="supports differ"):
        paired_same_support_delta({"a": 1.0, "b": 9.0}, {"a": 0.0})

    with pytest.raises(TypeError):
        paired_same_support_delta(
            {"a": 1.0, "b": 9.0},
            {"a": 0.0},
            support_ids=["a"],
        )


def test_paired_support_rejects_nan_key():
    nan_key = float("nan")
    with pytest.raises(SupportMismatchError, match="NaN-like"):
        paired_same_support_delta({nan_key: 1.0}, {nan_key: 0.0})


def test_weighted_support_requires_exact_same_finite_positive_support():
    out = weighted_same_support_delta(
        {"a": 1.0},
        {"a": 0.25},
        {"a": 2.0},
    )
    assert out["delta"] == pytest.approx(0.75)

    with pytest.raises(SupportMismatchError, match="supports differ"):
        weighted_same_support_delta(
            {"overlap": 1.0, "candidate_only": 100.0},
            {"overlap": 0.25},
            {"overlap": 2.0},
        )
    with pytest.raises(SupportMismatchError, match="must be > 0"):
        weighted_same_support_delta(
            {"a": 1.0},
            {"a": 0.0},
            {"a": 0.0},
        )
    with pytest.raises(TypeError):
        weighted_same_support_delta(
            {"a": 1.0, "b": 10.0},
            {"a": 0.0},
            {"a": 1.0},
            support_keys=["a"],
        )


def test_gate_conjunction_uses_frozen_contract_and_literal_true():
    assert fail_closed_gate_conjunction(
        {"primary": True, "matched": True, "structural": True},
        GATE_CONTRACT,
    )
    assert not fail_closed_gate_conjunction(
        {"primary": True, "matched": True},
        GATE_CONTRACT,
    )
    assert not fail_closed_gate_conjunction(
        {"primary": True, "matched": None, "structural": True},
        GATE_CONTRACT,
    )
    assert not fail_closed_gate_conjunction(
        {"primary": True, "matched": 1, "structural": True},
        GATE_CONTRACT,
    )
    assert not fail_closed_gate_conjunction(
        {"primary": True},
        object(),
    )


def test_direct_proof_construction_and_lookalikes_fail_closed(tmp_path: Path):
    with pytest.raises(DatasetIdentityError, match="authorize_dataset_access"):
        AuthorizedDataset(
            identity=IDENTITY,
            policy=POLICY,
            code_sha="0" * 40,
            repo_manifest_git_path="x",
            frozen_snapshot_git_path="y",
            runtime_snapshot_path=tmp_path / "z",
            partitions=(),
        )

    ctx = _authorized(tmp_path / "real")

    class FakeCodeFreeze:
        code_sha = ctx["code_sha"]

    class FakeAuthorizedDataset:
        policy = POLICY
        identity = IDENTITY

    with pytest.raises(CodeIdentityError, match="verify_git_freeze proof"):
        build_run_identity(
            hypothesis_id="B02_TEST",
            stage="development",
            code_freeze=FakeCodeFreeze(),
            authorized_dataset=ctx["authorized"],
            gate_contract=GATE_CONTRACT,
            command=["python", "-m", "fake"],
        )
    with pytest.raises(DatasetIdentityError, match="authorize_dataset_access proof"):
        build_run_identity(
            hypothesis_id="B02_TEST",
            stage="development",
            code_freeze=ctx["code_freeze"],
            authorized_dataset=FakeAuthorizedDataset(),
            gate_contract=GATE_CONTRACT,
            command=["python", "-m", "fake"],
        )


def test_run_identity_records_frozen_evidence_partitions_and_gate_contract(tmp_path: Path):
    ctx = _authorized(
        tmp_path,
        {
            "2020-01.parquet": b"a",
            "2021-01.parquet": b"b",
        },
    )
    identity = build_run_identity(
        hypothesis_id="B02_TEST",
        stage="development",
        code_freeze=ctx["code_freeze"],
        authorized_dataset=ctx["authorized"],
        gate_contract=GATE_CONTRACT,
        command=["python", "-m", "scripts.research.experiments.b02_test"],
        seeds={"bootstrap": 7, "matched": 3},
    )
    assert identity["code_sha"] == ctx["code_sha"]
    assert identity["code_tree_oid"]
    assert identity["dataset_id"] == IDENTITY.dataset_id
    assert identity["snapshot_id"] == IDENTITY.snapshot_id
    assert len(identity["partitions"]) == 2
    assert identity["promotion_gate_contract"]["required_gate_names"] == [
        "primary",
        "matched",
        "structural",
    ]
    assert identity["promotion_gate_contract"]["sha256"] == GATE_CONTRACT.sha256


def test_build_run_identity_rechecks_code_and_partition_bytes(tmp_path: Path):
    ctx = _authorized(tmp_path)
    (ctx["monthly"] / "2020-01.parquet").write_bytes(b"changed")
    with pytest.raises(DatasetIdentityError, match="checksum drift"):
        build_run_identity(
            hypothesis_id="B02_TEST",
            stage="development",
            code_freeze=ctx["code_freeze"],
            authorized_dataset=ctx["authorized"],
            gate_contract=GATE_CONTRACT,
            command=["python", "-m", "fake"],
        )


def test_provenance_and_result_artifact_are_immutable(tmp_path: Path):
    ctx = _authorized(tmp_path)
    identity = build_run_identity(
        hypothesis_id="B02_TEST",
        stage="development",
        code_freeze=ctx["code_freeze"],
        authorized_dataset=ctx["authorized"],
        gate_contract=GATE_CONTRACT,
        command=["python", "-m", "scripts.research.experiments.b02_test"],
        seeds={"bootstrap": 7},
    )
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


# ---------------------------------------------------------------------------
# CR-01: every PRESENT runtime output_checksums representation (top-level,
# identity_payload, or both) must independently equal the Git-frozen
# checksum map -- one present location must never silently shadow another.
# ---------------------------------------------------------------------------
def test_cr01_a_both_runtime_locations_present_and_correct_passes(tmp_path: Path):
    ctx = _authorized(tmp_path)
    runtime = json.loads(ctx["runtime_snapshot"].read_text(encoding="utf-8"))
    runtime["output_checksums"] = dict(runtime["identity_payload"]["output_checksums"])
    ctx["runtime_snapshot"].write_text(
        json.dumps(runtime, sort_keys=True), encoding="utf-8"
    )

    # Must not raise: both present locations agree with the frozen map.
    authorize_dataset_access(
        code_freeze=ctx["code_freeze"],
        dataset_root=ctx["dataset_root"],
        identity=IDENTITY,
        policy=POLICY,
    )


def test_cr01_b_top_level_correct_nested_incorrect_fails_closed(tmp_path: Path):
    ctx = _authorized(tmp_path)
    runtime = json.loads(ctx["runtime_snapshot"].read_text(encoding="utf-8"))
    # top-level copy taken BEFORE the nested corruption below -- stays correct.
    runtime["output_checksums"] = dict(runtime["identity_payload"]["output_checksums"])
    rel = next(iter(runtime["identity_payload"]["output_checksums"]))
    runtime["identity_payload"]["output_checksums"][rel] = "0" * 64
    ctx["runtime_snapshot"].write_text(
        json.dumps(runtime, sort_keys=True), encoding="utf-8"
    )

    with pytest.raises(DatasetIdentityError, match="identity_payload"):
        authorize_dataset_access(
            code_freeze=ctx["code_freeze"],
            dataset_root=ctx["dataset_root"],
            identity=IDENTITY,
            policy=POLICY,
        )


def test_cr01_c_nested_correct_top_level_incorrect_fails_closed(tmp_path: Path):
    ctx = _authorized(tmp_path)
    runtime = json.loads(ctx["runtime_snapshot"].read_text(encoding="utf-8"))
    correct = dict(runtime["identity_payload"]["output_checksums"])
    corrupted = dict(correct)
    rel = next(iter(corrupted))
    corrupted[rel] = "1" * 64
    runtime["output_checksums"] = corrupted
    # nested (identity_payload) is left untouched -- still correct.
    ctx["runtime_snapshot"].write_text(
        json.dumps(runtime, sort_keys=True), encoding="utf-8"
    )

    with pytest.raises(DatasetIdentityError, match="top-level"):
        authorize_dataset_access(
            code_freeze=ctx["code_freeze"],
            dataset_root=ctx["dataset_root"],
            identity=IDENTITY,
            policy=POLICY,
        )


def test_cr01_d_both_runtime_locations_missing_fails_closed(tmp_path: Path):
    ctx = _authorized(tmp_path)
    runtime = json.loads(ctx["runtime_snapshot"].read_text(encoding="utf-8"))
    del runtime["identity_payload"]["output_checksums"]
    assert "output_checksums" not in runtime
    ctx["runtime_snapshot"].write_text(
        json.dumps(runtime, sort_keys=True), encoding="utf-8"
    )

    with pytest.raises(DatasetIdentityError, match="no runtime output_checksums evidence"):
        authorize_dataset_access(
            code_freeze=ctx["code_freeze"],
            dataset_root=ctx["dataset_root"],
            identity=IDENTITY,
            policy=POLICY,
        )


# ---------------------------------------------------------------------------
# CR-02: `tuple(mapping)` yields mapping KEYS, not values -- a dict/Mapping
# passed to decision_t_ms/available_at_ms must be rejected explicitly, never
# silently reinterpreted as a timestamp sequence via generic iteration.
# ---------------------------------------------------------------------------
def test_cr02_rejects_mapping_for_decision_t_ms():
    t0 = 1_600_000_000_000
    # If the Mapping guard were missing, tuple({t0: "ignored"}) == (t0,) --
    # a "valid" single-timestamp tuple -- so this dict is deliberately
    # constructed to look like it WOULD silently succeed without the fix.
    with pytest.raises(LookaheadError, match="mapping"):
        assert_no_lookahead({t0: "ignored-value"}, [t0])


def test_cr02_rejects_mapping_for_available_at_ms():
    t0 = 1_600_000_000_000
    with pytest.raises(LookaheadError, match="mapping"):
        assert_no_lookahead([t0], {t0: "ignored-value"})


def test_cr02_ordinary_list_or_tuple_of_valid_ms_still_passes():
    t0 = 1_600_000_000_000
    assert_no_lookahead((t0, t0 + 500), (t0, t0 + 400))
    assert_no_lookahead([t0, t0 + 500], [t0, t0 + 400])
    assert_no_lookahead(np.int64(t0), np.int64(t0))


# ---------------------------------------------------------------------------
# CR-04: `set`/`frozenset` are unordered -- iterating one yields items in an
# implementation-defined order, which would silently break the positional
# decision/availability pairing `assert_no_lookahead` relies on for
# deterministic replay. Must be rejected before generic tuple(value)
# conversion, without affecting ordered list/tuple sequences.
# ---------------------------------------------------------------------------
def test_cr04_rejects_set_for_decision_t_ms():
    t0 = 1_600_000_000_000
    with pytest.raises(LookaheadError, match="unordered set"):
        assert_no_lookahead({t0, t0 + 500}, [t0, t0 + 400])


def test_cr04_rejects_set_for_available_at_ms():
    t0 = 1_600_000_000_000
    with pytest.raises(LookaheadError, match="unordered set"):
        assert_no_lookahead([t0, t0 + 500], {t0, t0 + 400})


def test_cr04_rejects_frozenset():
    t0 = 1_600_000_000_000
    with pytest.raises(LookaheadError, match="unordered set"):
        assert_no_lookahead(frozenset({t0, t0 + 500}), [t0, t0 + 400])
    with pytest.raises(LookaheadError, match="unordered set"):
        assert_no_lookahead([t0, t0 + 500], frozenset({t0, t0 + 400}))


def test_cr04_ordinary_list_or_tuple_still_passes():
    t0 = 1_600_000_000_000
    assert_no_lookahead((t0, t0 + 500), (t0, t0 + 400))
    assert_no_lookahead([t0, t0 + 500], [t0, t0 + 400])


# ---------------------------------------------------------------------------
# CR-03: OS/subprocess I/O failures inside `_run_git`/`_worktree_blob_oid`
# must be owned by CodeIdentityError, never leaked as a raw OSError.
# Deterministic monkeypatching only -- no chmod/permission-bit reliance.
# ---------------------------------------------------------------------------
def test_cr03_run_git_wraps_os_error_as_code_identity_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    from scripts.research.lib import research_harness

    code_repo = tmp_path / "code"
    sha, _ = _init_frozen_repo(code_repo, {})

    def _raise_oserror(*args, **kwargs):
        raise OSError(12, "Cannot allocate memory")

    monkeypatch.setattr(research_harness.subprocess, "run", _raise_oserror)

    with pytest.raises(CodeIdentityError, match="git command failed") as excinfo:
        verify_git_freeze(code_repo, sha)
    assert isinstance(excinfo.value.__cause__, OSError)


def test_cr03_worktree_blob_oid_wraps_symlink_read_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    from scripts.research.lib import research_harness

    code_repo = tmp_path / "code"
    code_repo.mkdir()
    _git(code_repo, "init")
    (code_repo / "target.txt").write_text("t\n", encoding="utf-8")
    os.symlink("target.txt", code_repo / "linked")
    _git(code_repo, "add", ".")
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=Harness Test",
            "-c",
            "user.email=harness@example.invalid",
            "commit",
            "-m",
            "freeze",
        ],
        cwd=code_repo,
        check=True,
        capture_output=True,
        text=True,
    )
    sha = _git(code_repo, "rev-parse", "HEAD")

    def _raise_oserror(path):
        raise OSError(13, "Permission denied")

    monkeypatch.setattr(research_harness.os, "readlink", _raise_oserror)

    with pytest.raises(
        CodeIdentityError, match="unable to read tracked symlink target"
    ) as excinfo:
        verify_git_freeze(code_repo, sha)
    assert isinstance(excinfo.value.__cause__, OSError)


def test_cr03_worktree_blob_oid_wraps_regular_file_read_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    code_repo = tmp_path / "code"
    sha, _ = _init_frozen_repo(code_repo, {})

    original_read_bytes = Path.read_bytes

    def _raise_for_tracked_txt(self, *args, **kwargs):
        if self.name == "tracked.txt":
            raise OSError(5, "Input/output error")
        return original_read_bytes(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_bytes", _raise_for_tracked_txt)

    with pytest.raises(
        CodeIdentityError, match="unable to read tracked worktree file"
    ) as excinfo:
        verify_git_freeze(code_repo, sha)
    assert isinstance(excinfo.value.__cause__, OSError)


# ---------------------------------------------------------------------------
# CR-05: a hollow AuthorizedDataset created by bypassing __post_init__ must
# fail at every use-site, not merely during normal dataclass construction.
# ---------------------------------------------------------------------------
def test_cr05_hollow_authorized_dataset_fails_at_use_time():
    forged = object.__new__(AuthorizedDataset)

    with pytest.raises(DatasetIdentityError, match="created by authorize_dataset_access"):
        forged.list_monthly_partitions()
    with pytest.raises(DatasetIdentityError, match="created by authorize_dataset_access"):
        forged.partition_evidence()
    with pytest.raises(DatasetIdentityError, match="created by authorize_dataset_access"):
        forged.assert_outcome_window(START_2020_MS, 0)


def test_cr05_mutated_partition_tuple_fails_proof_recheck(tmp_path: Path):
    ctx = _authorized(tmp_path)
    authorized = ctx["authorized"]
    evil = tmp_path / "evil.parquet"
    evil.write_bytes(b"evil")
    forged_partition = AuthorizedPartition(
        path=evil,
        relative_path="canonical/1m/monthly/2020-01.parquet",
        sha256=sha256_file(evil),
    )
    object.__setattr__(authorized, "partitions", (forged_partition,))

    with pytest.raises(DatasetIdentityError, match="partition proof mismatch"):
        authorized.list_monthly_partitions()


def test_cr05_monthly_directory_symlink_swap_fails_at_use_time(tmp_path: Path):
    ctx = _authorized(tmp_path)
    authorized = ctx["authorized"]
    monthly = ctx["monthly"]
    moved = tmp_path / "monthly-real"
    monthly.rename(moved)
    os.symlink(moved, monthly)

    with pytest.raises(DatasetIdentityError, match="became a symlink"):
        authorized.list_monthly_partitions()
