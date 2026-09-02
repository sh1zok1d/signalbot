"""Outcome-blind red-team tests for Batch02 durable evidence retention V1.

These tests use synthetic Git freezes, temporary directories, and temporary
local/bare Git remotes only. They must not open real CORE_BTC_BINANCE_V0
market partitions, 2025 validation, 2026 OOS, or any Batch02 market outcome.
"""
from __future__ import annotations

import hashlib
import json
import stat
import subprocess
from pathlib import Path

import pytest
import yaml

from scripts.research.lib import batch02_contracts
from scripts.research.lib.batch02_contracts import (
    Batch02ContractError,
    DurableEvidenceReservation,
    PostOutcomeRetentionFailure,
    PreOutcomeRetentionError,
    archive_batch02_result,
    persist_batch02_result,
    prepare_batch02_evidence_reservation,
    prepare_batch02_retained_run,
    prepare_batch02_run,
    verify_batch02_code,
)
from scripts.research.lib.batch02_evidence_retention import (
    POST_OUTCOME_STATE,
    artifact_relpath,
    evidence_ref_for,
    run_git,
    sanitize_remote_identity,
    sha256_bytes,
)
from scripts.research.lib.batch02_source_policy import (
    Batch02SourcePolicyError,
    validate_batch02_source_tree,
)
from scripts.research.lib.research_harness import (
    DatasetIdentityContract,
    OutcomeAccessPolicy,
    PromotionGateContract,
    VerifiedCodeFreeze,
    sha256_file,
    verify_git_freeze,
)


HYPOTHESIS = "B2-03_RETENTION_FIXTURE"
SNAPSHOT = "a" * 64
START_MS = 1_577_836_800_000
END_MS = 1_640_995_200_000
DATASET_ID = "SYNTHETIC_RETENTION_V1"
AUTHORIZE_CALLS: list[str] = []


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _commit(root: Path, message: str) -> None:
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=Retention Test",
            "-c",
            "user.email=retention@example.invalid",
            "commit",
            "-m",
            message,
        ],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )


def _init_bare(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["git", "init", "--bare", str(path)],
        check=True,
        capture_output=True,
        text=True,
    )
    return path


def _init_execution_repo(tmp_path: Path) -> tuple[Path, Path, str]:
    bare = _init_bare(tmp_path / "evidence.git")
    repo = tmp_path / "code"
    repo.mkdir()
    _git(repo, "init")
    (repo / ".gitignore").write_text("artifacts/\n", encoding="utf-8")
    (repo / "tracked.txt").write_text("frozen\n", encoding="utf-8")
    _git(repo, "add", ".")
    _commit(repo, "freeze")
    _git(repo, "remote", "add", "origin", str(bare.resolve()))
    sha = _git(repo, "rev-parse", "HEAD")
    return repo, bare, sha


def _reservation_kwargs(code_freeze, **overrides):
    payload = {
        "code_freeze": code_freeze,
        "hypothesis_id": HYPOTHESIS,
        "stage": "development",
        "dataset_id": DATASET_ID,
        "snapshot_id": SNAPSHOT,
        "start_inclusive_ms": START_MS,
        "end_exclusive_ms": END_MS,
        "allowed_years": (2020, 2021),
        "required_gate_names": ("primary", "matched"),
        "seeds": {"bootstrap": 7},
    }
    payload.update(overrides)
    return payload


def _reserve(repo: Path, sha: str, **overrides):
    freeze = verify_batch02_code(repo_root=repo, expected_code_sha=sha)
    return prepare_batch02_evidence_reservation(**_reservation_kwargs(freeze, **overrides))


def _remote_blob(bare: Path, ref: str, relative: str) -> bytes:
    return subprocess.run(
        ["git", "--git-dir", str(bare), "show", f"{ref}:{relative}"],
        check=True,
        capture_output=True,
    ).stdout


def _checkout_evidence(bare: Path, work: Path, evidence_ref: str) -> None:
    work.mkdir(parents=True)
    _git(work, "init")
    _git(work, "remote", "add", "origin", str(bare.resolve()))
    _git(work, "fetch", "--no-tags", "origin", evidence_ref)
    _git(work, "checkout", "--detach", "FETCH_HEAD")


def _init_dataset_and_code(tmp_path: Path) -> tuple[Path, Path, Path, str]:
    """Synthetic dataset + frozen code repo. Does not read real CORE partitions."""
    dataset_root = tmp_path / "dataset"
    monthly = dataset_root / "canonical" / "1m" / "monthly"
    monthly.mkdir(parents=True)
    (dataset_root / "reports").mkdir()
    partition = monthly / "2020-01.parquet"
    partition.write_bytes(b"synthetic-retention-partition")
    checksums = {
        partition.relative_to(dataset_root).as_posix(): sha256_file(partition)
    }

    bare = _init_bare(tmp_path / "evidence.git")
    repo = tmp_path / "code"
    repo.mkdir()
    _git(repo, "init")
    snapshot_git_path = "docs/research_data/CORE_BTC_BINANCE_V0/SNAPSHOT_SYNTHETIC.json"
    manifest_path = repo / "docs" / "manifests" / "CORE_BTC_BINANCE_V0.yaml"
    snapshot_path = repo / snapshot_git_path
    manifest_path.parent.mkdir(parents=True)
    snapshot_path.parent.mkdir(parents=True)
    manifest_path.write_text(
        yaml.safe_dump(
            {
                "dataset_id": "CORE_BTC_BINANCE_V0",
                "snapshot_id": SNAPSHOT,
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
                "snapshot_id": SNAPSHOT,
                "identity_payload": {
                    "dataset_id": "CORE_BTC_BINANCE_V0",
                    "output_checksums": checksums,
                },
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    (repo / ".gitignore").write_text("artifacts/\n", encoding="utf-8")
    (repo / "tracked.txt").write_text("frozen\n", encoding="utf-8")
    _git(repo, "add", ".")
    _commit(repo, "freeze")
    _git(repo, "remote", "add", "origin", str(bare.resolve()))
    sha = _git(repo, "rev-parse", "HEAD")

    runtime_snapshot = dataset_root / "reports" / "snapshot_manifest.json"
    runtime_snapshot.write_text(
        snapshot_path.read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    identity_copy = dataset_root / "reports" / "identity_payload.json"
    identity_copy.write_text(
        json.dumps(
            {"dataset_id": "CORE_BTC_BINANCE_V0", "output_checksums": checksums},
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    return repo, bare, dataset_root, sha


@pytest.fixture(autouse=True)
def _reset_authorize_probe(monkeypatch: pytest.MonkeyPatch):
    AUTHORIZE_CALLS.clear()
    original = batch02_contracts.authorize_dataset_access

    def probed(**kwargs):
        AUTHORIZE_CALLS.append("authorize_dataset_access")
        return original(**kwargs)

    monkeypatch.setattr(batch02_contracts, "authorize_dataset_access", probed)
    yield


def test_successful_reservation_archive_readback_and_frozen_worktree(tmp_path: Path):
    repo, bare, dataset_root, sha = _init_dataset_and_code(tmp_path)
    tree_before = _git(repo, "rev-parse", "HEAD^{tree}")
    tracked_before = _git(repo, "ls-tree", "-r", "HEAD")
    freeze = verify_batch02_code(repo_root=repo, expected_code_sha=sha)

    reservation = prepare_batch02_evidence_reservation(
        **_reservation_kwargs(
            freeze,
            dataset_id="CORE_BTC_BINANCE_V0",
        )
    )
    assert AUTHORIZE_CALLS == []
    remote_reservation = _remote_blob(bare, reservation.evidence_ref, "reservation.json")
    payload = json.loads(remote_reservation)
    assert payload["outcomes"] is None
    assert payload["kind"] == "batch02_pre_outcome_evidence_reservation"
    assert hashlib.sha256(remote_reservation).hexdigest() == reservation.reservation_sha256

    ctx = prepare_batch02_retained_run(
        reservation=reservation,
        outcome_access_acknowledged=True,
        dataset_root=dataset_root,
        command=("python", "-m", "b2_03_retention_fixture"),
    )
    assert AUTHORIZE_CALLS == ["authorize_dataset_access"]

    result_path = (
        repo
        / "artifacts"
        / "b2_03_retention_fixture"
        / "B2_03_RETENTION_FIXTURE_DEV_RESULTS.json"
    )
    digest = persist_batch02_result(
        result_path,
        {"status": "synthetic_closed", "note": "outcome-blind fixture"},
        run_context=ctx,
    )
    source = result_path.read_bytes()
    assert sha256_bytes(source) == digest

    receipt = archive_batch02_result(
        reservation=reservation,
        run_context=ctx,
        result_path=result_path,
        expected_sha256=digest,
    )
    remote_artifact = _remote_blob(bare, reservation.evidence_ref, receipt.evidence_path)
    assert remote_artifact == source
    assert sha256_bytes(remote_artifact) == digest
    assert len(remote_artifact) == len(source)
    assert receipt.artifact_sha256 == digest
    assert receipt.artifact_size_bytes == len(source)
    assert receipt.archive_commit_sha
    assert _HEX40(receipt.archive_commit_sha)
    remote_receipt = json.loads(_remote_blob(bare, reservation.evidence_ref, "receipt.json"))
    assert remote_receipt["artifact_sha256"] == digest
    assert "token" not in json.dumps(remote_receipt).lower()
    assert reservation.evidence_head_sha != receipt.archive_commit_sha

    log = subprocess.run(
        ["git", "--git-dir", str(bare), "log", "--oneline", reservation.evidence_ref],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert len(log.splitlines()) == 2
    assert _git(repo, "rev-parse", "HEAD^{tree}") == tree_before
    assert _git(repo, "ls-tree", "-r", "HEAD") == tracked_before
    verify_git_freeze(repo, sha)
    assert result_path.read_bytes() == source


def _HEX40(value: str) -> bool:
    return len(value) == 40 and all(ch in "0123456789abcdef" for ch in value)


def test_prepare_batch02_run_rejects_b2_03_with_typed_freeze(tmp_path: Path):
    repo, _bare, sha = _init_execution_repo(tmp_path)
    freeze = verify_batch02_code(repo_root=repo, expected_code_sha=sha)
    with pytest.raises(Batch02ContractError, match="B2-03\\+"):
        prepare_batch02_run(
            code_freeze=freeze,
            outcome_access_acknowledged=True,
            dataset_root=tmp_path,
            hypothesis_id=HYPOTHESIS,
            stage="development",
            command=("python", "-m", "x"),
            seeds={"bootstrap": 1},
            dataset_id=DATASET_ID,
            snapshot_id=SNAPSHOT,
            start_inclusive_ms=START_MS,
            end_exclusive_ms=END_MS,
            allowed_years=(2020, 2021),
            required_gate_names=("primary",),
        )
    assert AUTHORIZE_CALLS == []


def test_missing_origin_is_pre_outcome_and_does_not_authorize(tmp_path: Path):
    repo, _bare, sha = _init_execution_repo(tmp_path)
    _git(repo, "remote", "remove", "origin")
    freeze = verify_batch02_code(repo_root=repo, expected_code_sha=sha)
    with pytest.raises(PreOutcomeRetentionError, match="not configured"):
        prepare_batch02_evidence_reservation(**_reservation_kwargs(freeze))
    assert AUTHORIZE_CALLS == []


def test_invalid_remote_is_pre_outcome(tmp_path: Path):
    repo, _bare, sha = _init_execution_repo(tmp_path)
    _git(repo, "remote", "remove", "origin")
    _git(repo, "remote", "add", "origin", "https://example.com/not-signalbot.git")
    freeze = verify_batch02_code(repo_root=repo, expected_code_sha=sha)
    with pytest.raises(PreOutcomeRetentionError, match="canonical repository"):
        prepare_batch02_evidence_reservation(**_reservation_kwargs(freeze))
    assert AUTHORIZE_CALLS == []


def test_credential_bearing_origin_is_rejected_and_redacted(tmp_path: Path):
    repo, _bare, sha = _init_execution_repo(tmp_path)
    secret = "SUPERSECRETTOKEN"
    _git(repo, "remote", "remove", "origin")
    _git(
        repo,
        "remote",
        "add",
        "origin",
        f"https://{secret}@github.com/sh1zok1d/signalbot.git",
    )
    freeze = verify_batch02_code(repo_root=repo, expected_code_sha=sha)
    with pytest.raises(PreOutcomeRetentionError, match="credential-bearing") as exc:
        prepare_batch02_evidence_reservation(**_reservation_kwargs(freeze))
    assert secret not in str(exc.value)
    assert secret not in repr(exc.value)
    assert AUTHORIZE_CALLS == []


def test_sanitize_rejects_userinfo_urls():
    with pytest.raises(PreOutcomeRetentionError, match="credential-bearing"):
        sanitize_remote_identity("https://user:password@github.com/sh1zok1d/signalbot.git")
    with pytest.raises(PreOutcomeRetentionError, match="credential-bearing"):
        sanitize_remote_identity("https://TOKEN@github.com/attacker/exfil.git")


def test_push_failure_is_pre_outcome(tmp_path: Path):
    repo, bare, sha = _init_execution_repo(tmp_path)
    hook = bare / "hooks" / "pre-receive"
    hook.write_text("#!/bin/sh\necho rejected\nexit 1\n", encoding="utf-8")
    hook.chmod(hook.stat().st_mode | stat.S_IEXEC)
    freeze = verify_batch02_code(repo_root=repo, expected_code_sha=sha)
    with pytest.raises(PreOutcomeRetentionError):
        prepare_batch02_evidence_reservation(**_reservation_kwargs(freeze))
    assert AUTHORIZE_CALLS == []


def test_reservation_readback_failure_is_pre_outcome(tmp_path: Path):
    repo, bare, sha = _init_execution_repo(tmp_path)
    hook = bare / "hooks" / "post-receive"
    hook.write_text(
        "#!/bin/sh\nwhile read old new ref; do git update-ref -d \"$ref\"; done\n",
        encoding="utf-8",
    )
    hook.chmod(hook.stat().st_mode | stat.S_IEXEC)
    freeze = verify_batch02_code(repo_root=repo, expected_code_sha=sha)
    with pytest.raises(PreOutcomeRetentionError, match="not independently readable"):
        prepare_batch02_evidence_reservation(**_reservation_kwargs(freeze))
    assert AUTHORIZE_CALLS == []


def test_incompatible_existing_reservation_fails_closed(tmp_path: Path):
    repo, _bare, sha = _init_execution_repo(tmp_path)
    _reserve(repo, sha, dataset_id="FIRST_DATASET")
    with pytest.raises(PreOutcomeRetentionError, match="incompatible"):
        _reserve(repo, sha, dataset_id="SECOND_DATASET")
    assert AUTHORIZE_CALLS == []


def test_identical_existing_reservation_is_reused(tmp_path: Path):
    repo, _bare, sha = _init_execution_repo(tmp_path)
    first = _reserve(repo, sha)
    second = _reserve(repo, sha)
    assert first.reservation_sha256 == second.reservation_sha256
    assert first.evidence_head_sha == second.evidence_head_sha
    assert AUTHORIZE_CALLS == []


def test_forged_and_mutated_reservation_tokens_fail(tmp_path: Path):
    repo, _bare, sha = _init_execution_repo(tmp_path)
    real = _reserve(repo, sha)
    hollow = object.__new__(DurableEvidenceReservation)
    with pytest.raises(PreOutcomeRetentionError, match="minted"):
        hollow.assert_minted()
    with pytest.raises(PreOutcomeRetentionError, match="minted"):
        prepare_batch02_retained_run(
            reservation=hollow,
            outcome_access_acknowledged=True,
            dataset_root=tmp_path,
            command=("python", "-m", "x"),
        )
    with pytest.raises(PreOutcomeRetentionError, match="minted"):
        DurableEvidenceReservation(
            hypothesis_id=HYPOTHESIS,
            stage="development",
            code_sha=sha,
            code_tree="0" * 40,
            repo_root=repo,
            remote_repository_identity="local-git:/tmp",
            evidence_ref=real.evidence_ref,
            reservation_sha256="0" * 64,
            evidence_head_sha="0" * 40,
            dataset_id=DATASET_ID,
            snapshot_id=SNAPSHOT,
            start_inclusive_ms=START_MS,
            end_exclusive_ms=END_MS,
            allowed_years=(2020,),
            required_gate_names=("primary",),
            gate_contract_sha256="0" * 64,
            seeds={"bootstrap": 7},
        )
    stolen = DurableEvidenceReservation(
        hypothesis_id="B2-03_FORGED",
        stage="development",
        code_sha=real.code_sha,
        code_tree=real.code_tree,
        repo_root=real.repo_root,
        remote_repository_identity=real.remote_repository_identity,
        evidence_ref=real.evidence_ref,
        reservation_sha256=real.reservation_sha256,
        evidence_head_sha=real.evidence_head_sha,
        dataset_id=real.dataset_id,
        snapshot_id=real.snapshot_id,
        start_inclusive_ms=real.start_inclusive_ms,
        end_exclusive_ms=real.end_exclusive_ms,
        allowed_years=real.allowed_years,
        required_gate_names=real.required_gate_names,
        gate_contract_sha256=real.gate_contract_sha256,
        seeds=real.seeds,
        _mint_token=real._mint_token,
    )
    with pytest.raises(PreOutcomeRetentionError, match="forged|mutated|minted"):
        stolen.assert_minted()
    object.__setattr__(real, "hypothesis_id", "B2-03_MUTATED")
    with pytest.raises(PreOutcomeRetentionError, match="mutated|forged"):
        real.assert_minted()
    assert AUTHORIZE_CALLS == []


def test_path_traversal_hypothesis_id_is_rejected(tmp_path: Path):
    repo, _bare, sha = _init_execution_repo(tmp_path)
    freeze = verify_batch02_code(repo_root=repo, expected_code_sha=sha)
    with pytest.raises(PreOutcomeRetentionError):
        prepare_batch02_evidence_reservation(
            **_reservation_kwargs(freeze, hypothesis_id="B2-03/../../evil")
        )
    with pytest.raises(PreOutcomeRetentionError):
        prepare_batch02_evidence_reservation(
            **_reservation_kwargs(freeze, hypothesis_id="B2-03_EVIL/../x")
        )
    assert AUTHORIZE_CALLS == []


def test_dirty_code_freeze_is_pre_outcome(tmp_path: Path):
    repo, _bare, sha = _init_execution_repo(tmp_path)
    freeze = verify_batch02_code(repo_root=repo, expected_code_sha=sha)
    (repo / "tracked.txt").write_text("dirty\n", encoding="utf-8")
    with pytest.raises(Exception):
        prepare_batch02_evidence_reservation(**_reservation_kwargs(freeze))
    assert AUTHORIZE_CALLS == []


def test_caller_cannot_pass_arbitrary_remote(tmp_path: Path):
    repo, _bare, sha = _init_execution_repo(tmp_path)
    freeze = verify_batch02_code(repo_root=repo, expected_code_sha=sha)
    with pytest.raises(TypeError):
        prepare_batch02_evidence_reservation(
            **_reservation_kwargs(freeze),
            evidence_remote="https://example.com/exfil.git",  # type: ignore[call-arg]
        )


def test_exact_byte_failures_after_persist(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    repo, bare, dataset_root, sha = _init_dataset_and_code(tmp_path)
    freeze = verify_batch02_code(repo_root=repo, expected_code_sha=sha)
    reservation = prepare_batch02_evidence_reservation(
        **_reservation_kwargs(freeze, dataset_id="CORE_BTC_BINANCE_V0")
    )
    ctx = prepare_batch02_retained_run(
        reservation=reservation,
        outcome_access_acknowledged=True,
        dataset_root=dataset_root,
        command=("python", "-m", "b2_03_retention_fixture"),
    )
    result_path = (
        repo
        / "artifacts"
        / "b2_03_retention_fixture"
        / "B2_03_RETENTION_FIXTURE_DEV_RESULTS.json"
    )
    digest = persist_batch02_result(
        result_path,
        {"status": "synthetic_closed"},
        run_context=ctx,
    )
    original = result_path.read_bytes()

    result_path.write_bytes(original + b"\n")
    with pytest.raises(PostOutcomeRetentionFailure, match=POST_OUTCOME_STATE):
        archive_batch02_result(
            reservation=reservation,
            run_context=ctx,
            result_path=result_path,
            expected_sha256=digest,
        )
    assert result_path.exists()
    result_path.write_bytes(original)

    mutated = original.replace(b"\n", b"\r\n")
    if mutated == original:
        mutated = original + b"\r\n"
    result_path.write_bytes(mutated)
    with pytest.raises(PostOutcomeRetentionFailure, match=POST_OUTCOME_STATE):
        archive_batch02_result(
            reservation=reservation,
            run_context=ctx,
            result_path=result_path,
            expected_sha256=digest,
        )
    result_path.write_bytes(original)

    parsed = json.loads(original)
    reserialized = (json.dumps(parsed, indent=4) + "\n").encode("utf-8")
    assert reserialized != original
    result_path.write_bytes(reserialized)
    with pytest.raises(PostOutcomeRetentionFailure, match=POST_OUTCOME_STATE):
        archive_batch02_result(
            reservation=reservation,
            run_context=ctx,
            result_path=result_path,
            expected_sha256=digest,
        )
    result_path.write_bytes(original)
    assert sha256_file(result_path) == digest
    del bare


def test_readback_sha_and_size_mismatch_fail(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    repo, _bare, dataset_root, sha = _init_dataset_and_code(tmp_path)
    freeze = verify_batch02_code(repo_root=repo, expected_code_sha=sha)
    reservation = prepare_batch02_evidence_reservation(
        **_reservation_kwargs(freeze, dataset_id="CORE_BTC_BINANCE_V0")
    )
    ctx = prepare_batch02_retained_run(
        reservation=reservation,
        outcome_access_acknowledged=True,
        dataset_root=dataset_root,
        command=("python", "-m", "b2_03_retention_fixture"),
    )
    result_path = (
        repo
        / "artifacts"
        / "b2_03_retention_fixture"
        / "B2_03_RETENTION_FIXTURE_DEV_RESULTS.json"
    )
    digest = persist_batch02_result(
        result_path,
        {"status": "synthetic_closed"},
        run_context=ctx,
    )
    source = result_path.read_bytes()

    import scripts.research.lib.batch02_evidence_retention as retention

    original_readback = retention._independent_readback

    def mutated_readback(**kwargs):
        commit, data = original_readback(**kwargs)
        if kwargs["relative"].endswith(".json") and kwargs["relative"] != "reservation.json" and kwargs["relative"] != "receipt.json":
            return commit, data + b" "
        return commit, data

    monkeypatch.setattr(retention, "_independent_readback", mutated_readback)
    with pytest.raises(PostOutcomeRetentionFailure, match=POST_OUTCOME_STATE):
        archive_batch02_result(
            reservation=reservation,
            run_context=ctx,
            result_path=result_path,
            expected_sha256=digest,
        )
    assert result_path.read_bytes() == source

    def size_lie(**kwargs):
        commit, data = original_readback(**kwargs)
        if kwargs["relative"].endswith(".json") and "batch02/" in kwargs["relative"]:
            lied = data + b"X"
            monkeypatch.setattr(
                retention,
                "sha256_bytes",
                lambda value, _orig=retention.sha256_bytes, _src=source: (
                    hashlib.sha256(_src).hexdigest()
                    if value == lied
                    else _orig(value)
                ),
            )
            return commit, lied
        return commit, data

    monkeypatch.setattr(retention, "_independent_readback", size_lie)
    with pytest.raises(PostOutcomeRetentionFailure, match=POST_OUTCOME_STATE):
        archive_batch02_result(
            reservation=reservation,
            run_context=ctx,
            result_path=result_path,
            expected_sha256=digest,
        )
    assert result_path.exists()


def test_append_only_rejects_different_digest_and_ref_drift(tmp_path: Path):
    repo, bare, dataset_root, sha = _init_dataset_and_code(tmp_path)
    freeze = verify_batch02_code(repo_root=repo, expected_code_sha=sha)
    reservation = prepare_batch02_evidence_reservation(
        **_reservation_kwargs(freeze, dataset_id="CORE_BTC_BINANCE_V0")
    )
    ctx = prepare_batch02_retained_run(
        reservation=reservation,
        outcome_access_acknowledged=True,
        dataset_root=dataset_root,
        command=("python", "-m", "b2_03_retention_fixture"),
    )
    result_path = (
        repo
        / "artifacts"
        / "b2_03_retention_fixture"
        / "B2_03_RETENTION_FIXTURE_DEV_RESULTS.json"
    )
    digest = persist_batch02_result(
        result_path,
        {"status": "synthetic_closed"},
        run_context=ctx,
    )
    source = result_path.read_bytes()
    relative = artifact_relpath(HYPOTHESIS, reservation.code_sha, digest)

    work = tmp_path / "drift"
    _checkout_evidence(bare, work, reservation.evidence_ref)
    dest = work / relative
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(b'{"tampered":true}\n')
    _git(work, "add", "--", relative)
    _commit(work, "tamper")
    _git(work, "push", "origin", f"HEAD:{reservation.evidence_ref}")

    with pytest.raises(PostOutcomeRetentionFailure, match=POST_OUTCOME_STATE):
        archive_batch02_result(
            reservation=reservation,
            run_context=ctx,
            result_path=result_path,
            expected_sha256=digest,
        )
    assert result_path.read_bytes() == source
    assert result_path.exists()


def test_ref_drift_before_outcomes_is_pre_outcome(tmp_path: Path):
    repo, bare, sha = _init_execution_repo(tmp_path)
    reservation = _reserve(repo, sha)
    work = tmp_path / "drift"
    _checkout_evidence(bare, work, reservation.evidence_ref)
    (work / "extra.txt").write_text("drift\n", encoding="utf-8")
    _git(work, "add", "extra.txt")
    _commit(work, "drift")
    _git(work, "push", "origin", f"HEAD:{reservation.evidence_ref}")
    with pytest.raises(PreOutcomeRetentionError, match="drifted"):
        prepare_batch02_retained_run(
            reservation=reservation,
            outcome_access_acknowledged=True,
            dataset_root=dataset_root if False else tmp_path,
            command=("python", "-m", "x"),
        )
    assert AUTHORIZE_CALLS == []


def test_force_git_args_are_rejected():
    with pytest.raises(PreOutcomeRetentionError, match="force"):
        run_git(Path("/tmp"), ["push", "--force", "origin", "HEAD"])
    with pytest.raises(PreOutcomeRetentionError, match="force"):
        run_git(Path("/tmp"), ["push", "origin", "+HEAD:refs/heads/x"])


def test_post_outcome_push_failure_preserves_local_result_and_forbids_rerun(
    tmp_path: Path,
):
    repo, bare, dataset_root, sha = _init_dataset_and_code(tmp_path)
    freeze = verify_batch02_code(repo_root=repo, expected_code_sha=sha)
    reservation = prepare_batch02_evidence_reservation(
        **_reservation_kwargs(freeze, dataset_id="CORE_BTC_BINANCE_V0")
    )
    ctx = prepare_batch02_retained_run(
        reservation=reservation,
        outcome_access_acknowledged=True,
        dataset_root=dataset_root,
        command=("python", "-m", "b2_03_retention_fixture"),
    )
    result_path = (
        repo
        / "artifacts"
        / "b2_03_retention_fixture"
        / "B2_03_RETENTION_FIXTURE_DEV_RESULTS.json"
    )
    digest = persist_batch02_result(
        result_path,
        {"status": "synthetic_closed"},
        run_context=ctx,
    )
    original = result_path.read_bytes()
    lock_dir = result_path.parent / ".batch02_evidence_locks"
    assert lock_dir.exists()

    hook = bare / "hooks" / "pre-receive"
    hook.write_text("#!/bin/sh\necho archive-denied\nexit 1\n", encoding="utf-8")
    hook.chmod(hook.stat().st_mode | stat.S_IEXEC)

    with pytest.raises(PostOutcomeRetentionFailure) as exc:
        archive_batch02_result(
            reservation=reservation,
            run_context=ctx,
            result_path=result_path,
            expected_sha256=digest,
        )
    err = exc.value
    assert err.outcome_consumed is True
    assert err.rerun_authorized is False
    assert err.state == POST_OUTCOME_STATE
    assert result_path.exists()
    assert result_path.read_bytes() == original
    assert sha256_bytes(original) == digest
    assert lock_dir.exists()
    assert list(lock_dir.iterdir())
    sidecar = result_path.with_name(result_path.name + ".POST_OUTCOME_RETENTION_FAILURE.json")
    assert sidecar.exists()
    recovery = json.loads(sidecar.read_text(encoding="utf-8"))
    assert recovery["rerun_authorized"] is False
    assert recovery["outcome_consumed"] is True
    reservation.assert_minted()
    remote_reservation = _remote_blob(bare, reservation.evidence_ref, "reservation.json")
    assert hashlib.sha256(remote_reservation).hexdigest() == reservation.reservation_sha256

    with pytest.raises(Exception):
        persist_batch02_result(
            result_path,
            {"status": "retry"},
            run_context=ctx,
        )
    assert result_path.read_bytes() == original


def test_run_git_does_not_use_shell():
    source = Path("scripts/research/lib/batch02_evidence_retention.py").read_text(
        encoding="utf-8"
    )
    assert "shell=True" not in source
    assert "subprocess.run" in source
    assert "subprocess.run" in source


def test_source_policy_b2_03_requires_retention_ceremony_and_rejects_old_prepare(
    tmp_path: Path,
):
    repo = tmp_path / "repo"
    research = repo / "scripts" / "research"
    research.mkdir(parents=True)
    (repo / "scripts" / "__init__.py").write_text("", encoding="utf-8")
    (research / "__init__.py").write_text("", encoding="utf-8")
    (research / "b2_03_bad.py").write_text(
        """
from scripts.research.lib.batch02_contracts import (
    verify_batch02_code,
    prepare_batch02_run,
    persist_batch02_result,
)

def main():
    verify_batch02_code(repo_root=ROOT, expected_code_sha=SHA)
    ctx = prepare_batch02_run(
        code_freeze=FREEZE,
        outcome_access_acknowledged=True,
        dataset_root=ROOT,
        identity=IDENTITY,
        policy=POLICY,
        gate_contract=GATES,
        hypothesis_id="B2-03",
        stage="development",
        command=("python", "-m", "b2_03"),
        seeds={},
    )
    persist_batch02_result(PATH, {}, run_context=ctx)
""",
        encoding="utf-8",
    )
    with pytest.raises(Batch02SourcePolicyError, match="B2-03\\+|durable evidence|missing canonical"):
        validate_batch02_source_tree(research, repo_root=repo)

    (research / "b2_03_bad.py").unlink()
    (research / "b2_03_good.py").write_text(
        """
from scripts.research.lib.batch02_contracts import (
    verify_batch02_code,
    prepare_batch02_evidence_reservation,
    prepare_batch02_retained_run,
    persist_batch02_result,
    archive_batch02_result,
)

def main():
    freeze = verify_batch02_code(repo_root=ROOT, expected_code_sha=SHA)
    reservation = prepare_batch02_evidence_reservation(
        code_freeze=freeze,
        hypothesis_id="B2-03_X",
        stage="development",
        dataset_id="D",
        snapshot_id="S",
        start_inclusive_ms=1,
        end_exclusive_ms=2,
        allowed_years=(2020,),
        required_gate_names=("g",),
        seeds={"bootstrap": 1},
    )
    ctx = prepare_batch02_retained_run(
        reservation=reservation,
        outcome_access_acknowledged=True,
        dataset_root=ROOT,
        command=("python", "-m", "b2_03"),
    )
    persist_batch02_result(PATH, {}, run_context=ctx)
    archive_batch02_result(
        reservation=reservation,
        run_context=ctx,
        result_path=PATH,
        expected_sha256=SHA256,
    )
""",
        encoding="utf-8",
    )
    validate_batch02_source_tree(research, repo_root=repo)


def test_historical_prepare_still_works_for_b2_02(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    calls: list[str] = []

    class Authorized:
        def assert_minted(self):
            return None

    monkeypatch.setattr(
        batch02_contracts.Batch02RunContext,
        "assert_minted",
        lambda self: None,
    )
    monkeypatch.setattr(
        batch02_contracts,
        "authorize_dataset_access",
        lambda **kwargs: calls.append("auth") or Authorized(),
    )
    monkeypatch.setattr(
        batch02_contracts,
        "build_run_identity",
        lambda **kwargs: {"hypothesis_id": kwargs["hypothesis_id"], "stage": kwargs["stage"]},
    )
    freeze = object.__new__(VerifiedCodeFreeze)
    ctx = prepare_batch02_run(
        code_freeze=freeze,
        outcome_access_acknowledged=True,
        dataset_root=tmp_path,
        identity=DatasetIdentityContract(dataset_id="CORE", snapshot_id="snap"),
        policy=OutcomeAccessPolicy(
            stage="development",
            start_inclusive_ms=START_MS,
            end_exclusive_ms=END_MS,
            allowed_years=(2020, 2021),
        ),
        gate_contract=PromotionGateContract(("primary",)),
        hypothesis_id="B2-02_BOUNDARY_INTERACTION_PATH",
        stage="development",
        command=("python", "-m", "b2_02"),
        seeds={"bootstrap": 1},
    )
    assert calls == ["auth"]
    assert ctx.run_identity["hypothesis_id"] == "B2-02_BOUNDARY_INTERACTION_PATH"


def test_evidence_ref_stays_in_namespace():
    ref = evidence_ref_for(HYPOTHESIS, "a" * 40)
    assert ref.startswith("refs/heads/research-evidence/batch02/")
    with pytest.raises(PreOutcomeRetentionError):
        evidence_ref_for("B2-03/evil", "a" * 40)
