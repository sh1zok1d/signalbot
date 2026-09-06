"""Synthetic tests for Batch02 large-artifact exact-byte archival.

These tests never open CORE_BTC_BINANCE_V0, 2025, 2026, or any real
Batch02 market artifact. Thresholds and chunk sizes are monkeypatched
to tiny values so the chunked path can be exercised with small bytes.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from scripts.research.lib import batch02_evidence_retention as retention
from scripts.research.lib.batch02_contracts import (
    archive_batch02_result,
    persist_batch02_retained_result,
    prepare_batch02_retained_run,
    recover_claimed_batch02_artifact,
)
from scripts.research.lib.batch02_evidence_retention import (
    ARCHIVE_REPRESENTATION_RAW_CHUNKS,
    ARCHIVE_REPRESENTATION_SINGLE_BLOB,
    CHUNKED_ENCODING,
    GITHUB_REGULAR_GIT_OBJECT_LIMIT_BYTES,
    POST_OUTCOME_STATE,
    RAW_CHUNK_SIZE_BYTES,
    RECEIPT_BLOB_PATH,
    SAFE_SINGLE_BLOB_THRESHOLD_BYTES,
    STATE_ARCHIVED,
    STATE_CLAIMED,
    STATE_UNKNOWN,
    artifact_relpath,
    build_raw_chunk_manifest,
    chunked_manifest_relpath,
    chunked_part_relpath,
    classify_evidence_tree,
    clear_batch02_retention_runtime_state,
    reconstruct_raw_chunks,
    sha256_bytes,
    split_raw_bytes,
    uses_raw_chunk_archive,
    PostOutcomeRetentionFailure,
)
from scripts.research.lib.batch02_source_policy import validate_batch02_source_tree
from scripts.research.lib.research_harness import CodeIdentityError, verify_git_freeze
from tests.research.test_batch02_durable_evidence_retention import (
    _HEX40,
    _checkout_evidence,
    _commit,
    _git,
    _init_dataset_and_code,
    _remote_blob,
    _remote_tree,
    _reserve,
    _result_path,
)


def _hex64(value: str) -> bool:
    return len(value) == 64 and all(ch in "0123456789abcdef" for ch in value)


def test_configured_limits_stay_below_github_object_cap():
    assert RAW_CHUNK_SIZE_BYTES == 64 * 1024 * 1024
    assert SAFE_SINGLE_BLOB_THRESHOLD_BYTES == 90 * 1024 * 1024
    assert RAW_CHUNK_SIZE_BYTES < GITHUB_REGULAR_GIT_OBJECT_LIMIT_BYTES
    assert SAFE_SINGLE_BLOB_THRESHOLD_BYTES < GITHUB_REGULAR_GIT_OBJECT_LIMIT_BYTES


def test_threshold_boundary_selects_v1_or_chunks(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        "scripts.research.lib.batch02_evidence_retention.SAFE_SINGLE_BLOB_THRESHOLD_BYTES",
        8,
    )
    assert uses_raw_chunk_archive(8) is False
    assert uses_raw_chunk_archive(9) is True


def test_split_and_reconstruct_are_exact_and_deterministic():
    source = bytes(range(256)) * 3 + b"tail"
    chunks = split_raw_bytes(source, chunk_size_bytes=64)
    assert all(len(chunk) <= 64 for chunk in chunks)
    assert b"".join(chunks) == source
    assert sha256_bytes(b"".join(chunks)) == sha256_bytes(source)
    again = split_raw_bytes(source, chunk_size_bytes=64)
    assert again == chunks


def test_chunk_size_never_exceeds_configured_max(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        "scripts.research.lib.batch02_evidence_retention.RAW_CHUNK_SIZE_BYTES",
        16,
    )
    with pytest.raises(Exception, match="exceeds the configured maximum"):
        split_raw_bytes(b"0123456789abcdef!", chunk_size_bytes=17)


def _synthetic_manifest(source: bytes, chunk_size: int = 8):
    digest = sha256_bytes(source)
    code_sha = "a" * 40
    chunks = split_raw_bytes(source, chunk_size_bytes=chunk_size)
    manifest = build_raw_chunk_manifest(
        hypothesis_id="B2-03_RETENTION_FIXTURE",
        code_sha=code_sha,
        artifact_sha256=digest,
        artifact_size_bytes=len(source),
        chunk_size_bytes=chunk_size,
        chunks=chunks,
    )
    blobs = {
        chunked_part_relpath("B2-03_RETENTION_FIXTURE", code_sha, digest, index): chunk
        for index, chunk in enumerate(chunks)
    }
    return manifest, blobs, digest


def test_reconstruct_matches_original_digest():
    source = b"exact-byte-payload-" + bytes(range(80))
    manifest, blobs, digest = _synthetic_manifest(source)
    reconstructed = reconstruct_raw_chunks(manifest, blobs)
    assert reconstructed == source
    assert sha256_bytes(reconstructed) == digest
    assert len(reconstructed) == len(source)


def test_missing_chunk_fails():
    source = b"0123456789abcdef"
    manifest, blobs, _digest = _synthetic_manifest(source, chunk_size=4)
    missing = next(iter(blobs))
    blobs.pop(missing)
    with pytest.raises(Exception, match="missing|count"):
        reconstruct_raw_chunks(manifest, blobs)


def test_duplicated_chunk_fails():
    source = b"0123456789abcdef"
    manifest, blobs, _digest = _synthetic_manifest(source, chunk_size=4)
    entries = list(manifest["chunks"])
    entries.append(dict(entries[0]))
    manifest["chunks"] = entries
    manifest["chunk_count"] = len(entries)
    with pytest.raises(Exception, match="duplicated|order"):
        reconstruct_raw_chunks(manifest, blobs)


def test_reordered_chunk_fails():
    source = b"0123456789abcdef"
    manifest, blobs, _digest = _synthetic_manifest(source, chunk_size=4)
    manifest["chunks"] = list(reversed(list(manifest["chunks"])))
    with pytest.raises(Exception, match="ascending order"):
        reconstruct_raw_chunks(manifest, blobs)


def test_corrupted_chunk_fails():
    source = b"0123456789abcdef"
    manifest, blobs, _digest = _synthetic_manifest(source, chunk_size=4)
    path = next(iter(blobs))
    blobs[path] = blobs[path][:-1] + b"X"
    with pytest.raises(Exception, match="digest"):
        reconstruct_raw_chunks(manifest, blobs)


def test_manifest_tamper_fails():
    source = b"0123456789abcdef"
    manifest, blobs, _digest = _synthetic_manifest(source, chunk_size=4)
    manifest["encoding"] = "json_lines"
    with pytest.raises(Exception, match="encoding"):
        reconstruct_raw_chunks(manifest, blobs)


def test_wrong_total_size_fails():
    source = b"0123456789abcdef"
    manifest, blobs, _digest = _synthetic_manifest(source, chunk_size=4)
    manifest["artifact_size_bytes"] = len(source) + 1
    with pytest.raises(Exception, match="size"):
        reconstruct_raw_chunks(manifest, blobs)


def test_wrong_full_sha_fails():
    source = b"0123456789abcdef"
    manifest, blobs, _digest = _synthetic_manifest(source, chunk_size=4)
    manifest["artifact_sha256"] = "b" * 64
    with pytest.raises(Exception, match="digest"):
        reconstruct_raw_chunks(manifest, blobs)


def test_classify_chunked_tree_and_reject_mixed_or_reordered_parts():
    prefix = "batch02/B2-03/" + ("a" * 40) + "/" + ("b" * 64)
    claimed = ("reservation.json", "outcome_claim.json")
    assert classify_evidence_tree(claimed) == STATE_CLAIMED
    archived = {
        "reservation.json",
        "outcome_claim.json",
        "receipt.json",
        f"{prefix}/manifest.json",
        f"{prefix}/chunks/00000.part",
        f"{prefix}/chunks/00001.part",
    }
    assert classify_evidence_tree(archived) == STATE_ARCHIVED
    only_first = set(archived)
    only_first.remove(f"{prefix}/chunks/00001.part")
    assert classify_evidence_tree(only_first) == STATE_ARCHIVED
    missing_zero = set(archived)
    missing_zero.remove(f"{prefix}/chunks/00000.part")
    assert classify_evidence_tree(missing_zero) == STATE_UNKNOWN
    gap = set(archived)
    gap.remove(f"{prefix}/chunks/00000.part")
    gap.add(f"{prefix}/chunks/00002.part")
    assert classify_evidence_tree(gap) == STATE_UNKNOWN
    mixed = set(archived)
    mixed.add(f"{prefix}.json")
    assert classify_evidence_tree(mixed) == STATE_UNKNOWN


def _persist_payload(repo: Path, ctx, payload: bytes):
    result_path = _result_path(repo)
    persisted = persist_batch02_retained_result(
        result_path,
        {"status": "synthetic_closed", "blob": payload.hex()},
        run_context=ctx,
    )
    # Persist writes JSON. For large-path tests we overwrite the persisted
    # file with raw synthetic bytes and keep the minted proof aligned by
    # using a payload whose JSON already exceeds the monkeypatched
    # threshold, so we do not rewrite scientific artifacts. The JSON bytes
    # themselves are the artifact.
    source = result_path.read_bytes()
    return result_path, persisted, source


def _claimed_run(tmp_path: Path):
    repo, bare, dataset_root, sha = _init_dataset_and_code(tmp_path)
    reservation = _reserve(repo, sha, bare, dataset_id="CORE_BTC_BINANCE_V0")
    ctx = prepare_batch02_retained_run(
        reservation=reservation,
        outcome_access_acknowledged=True,
        dataset_root=dataset_root,
        command=("python", "-m", "b2_03_retention_fixture"),
    )
    return repo, bare, reservation, ctx


def test_small_artifact_keeps_v1_single_file_semantics(tmp_path: Path):
    repo, bare, reservation, ctx = _claimed_run(tmp_path)
    result_path, persisted, source = _persist_payload(repo, ctx, b"tiny")
    assert uses_raw_chunk_archive(len(source)) is False
    receipt = archive_batch02_result(persisted_result=persisted, run_context=ctx)
    expected = artifact_relpath(
        reservation.hypothesis_id, reservation.code_sha, persisted.artifact_sha256
    )
    assert receipt.evidence_path == expected
    assert _remote_blob(bare, reservation.evidence_ref, expected) == source
    remote_receipt = json.loads(_remote_blob(bare, reservation.evidence_ref, RECEIPT_BLOB_PATH))
    assert "archive_representation" not in remote_receipt
    names = set(_remote_tree(bare, reservation.evidence_ref))
    assert expected in names
    assert not any(name.endswith("/manifest.json") for name in names)


def test_large_artifact_uses_raw_chunks_and_reconstructs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(
        "scripts.research.lib.batch02_evidence_retention.SAFE_SINGLE_BLOB_THRESHOLD_BYTES",
        32,
    )
    monkeypatch.setattr(
        "scripts.research.lib.batch02_evidence_retention.RAW_CHUNK_SIZE_BYTES",
        16,
    )
    repo, bare, reservation, ctx = _claimed_run(tmp_path)
    claim_bytes = _remote_blob(bare, reservation.evidence_ref, "outcome_claim.json")
    reservation_bytes = _remote_blob(bare, reservation.evidence_ref, "reservation.json")
    claim_head = reservation.evidence_head_sha
    # After claim the head is the claim commit, not the reservation commit.
    import subprocess

    claim_head = subprocess.run(
        ["git", "--git-dir", str(bare), "rev-parse", reservation.evidence_ref],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip().lower()
    result_path, persisted, source = _persist_payload(
        repo, ctx, b"SYNTHETIC-LARGE-ARTIFACT-BYTES"
    )
    assert len(source) > 32
    receipt = archive_batch02_result(persisted_result=persisted, run_context=ctx)
    manifest_path = chunked_manifest_relpath(
        reservation.hypothesis_id, reservation.code_sha, persisted.artifact_sha256
    )
    assert receipt.evidence_path == manifest_path
    names = set(_remote_tree(bare, reservation.evidence_ref))
    assert manifest_path in names
    assert artifact_relpath(
        reservation.hypothesis_id, reservation.code_sha, persisted.artifact_sha256
    ) not in names
    manifest = json.loads(_remote_blob(bare, reservation.evidence_ref, manifest_path))
    assert manifest["encoding"] == CHUNKED_ENCODING
    assert all(int(entry["size_bytes"]) <= 16 for entry in manifest["chunks"])
    blobs = {
        entry["path"]: _remote_blob(bare, reservation.evidence_ref, entry["path"])
        for entry in manifest["chunks"]
    }
    reconstructed = reconstruct_raw_chunks(manifest, blobs)
    assert reconstructed == source
    assert sha256_bytes(reconstructed) == persisted.artifact_sha256
    assert len(reconstructed) == len(source)
    remote_receipt = json.loads(_remote_blob(bare, reservation.evidence_ref, RECEIPT_BLOB_PATH))
    assert remote_receipt["archive_representation"] == ARCHIVE_REPRESENTATION_RAW_CHUNKS
    assert remote_receipt["manifest_path"] == manifest_path
    assert remote_receipt["chunk_count"] == len(manifest["chunks"])
    assert remote_receipt["chunk_size_bytes"] == 16
    assert _hex64(remote_receipt["manifest_sha256"])
    assert remote_receipt["recovery_code_sha"] == reservation.code_sha
    assert "token" not in json.dumps(remote_receipt).lower()
    assert _remote_blob(bare, reservation.evidence_ref, "reservation.json") == reservation_bytes
    assert _remote_blob(bare, reservation.evidence_ref, "outcome_claim.json") == claim_bytes
    parent = subprocess.run(
        [
            "git",
            "--git-dir",
            str(bare),
            "rev-parse",
            f"{reservation.evidence_ref}^",
        ],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip().lower()
    assert parent == claim_head
    assert _HEX40(receipt.archive_commit_sha)
    assert result_path.read_bytes() == source


def test_second_archive_attempt_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        "scripts.research.lib.batch02_evidence_retention.SAFE_SINGLE_BLOB_THRESHOLD_BYTES",
        32,
    )
    monkeypatch.setattr(
        "scripts.research.lib.batch02_evidence_retention.RAW_CHUNK_SIZE_BYTES",
        16,
    )
    repo, bare, reservation, ctx = _claimed_run(tmp_path)
    _result_path_obj, persisted, source = _persist_payload(
        repo, ctx, b"SYNTHETIC-LARGE-ARTIFACT-BYTES"
    )
    archive_batch02_result(persisted_result=persisted, run_context=ctx)
    from scripts.research.lib.batch02_evidence_retention import POST_OUTCOME_STATE, PostOutcomeRetentionFailure

    with pytest.raises(PostOutcomeRetentionFailure, match=POST_OUTCOME_STATE):
        archive_batch02_result(persisted_result=persisted, run_context=ctx)
    assert _result_path(repo).read_bytes() == source


def test_claim_head_drift_fails_chunked_archive(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(
        "scripts.research.lib.batch02_evidence_retention.SAFE_SINGLE_BLOB_THRESHOLD_BYTES",
        32,
    )
    monkeypatch.setattr(
        "scripts.research.lib.batch02_evidence_retention.RAW_CHUNK_SIZE_BYTES",
        16,
    )
    from tests.research.test_batch02_durable_evidence_retention import (
        _checkout_evidence,
        _commit,
        _git,
    )
    from scripts.research.lib.batch02_evidence_retention import (
        POST_OUTCOME_STATE,
        PostOutcomeRetentionFailure,
    )

    repo, bare, reservation, ctx = _claimed_run(tmp_path)
    result_path, persisted, source = _persist_payload(
        repo, ctx, b"SYNTHETIC-LARGE-ARTIFACT-BYTES"
    )
    work = tmp_path / "drift"
    _checkout_evidence(bare, work, reservation.evidence_ref)
    (work / "extra.txt").write_text("unknown intermediate\n", encoding="utf-8")
    _git(work, "add", "extra.txt")
    _commit(work, "unknown-intermediate")
    _git(work, "push", "origin", f"HEAD:{reservation.evidence_ref}")
    with pytest.raises(PostOutcomeRetentionFailure, match=POST_OUTCOME_STATE):
        archive_batch02_result(persisted_result=persisted, run_context=ctx)
    assert result_path.read_bytes() == source


def test_force_push_still_absent():
    source = Path(
        "scripts/research/lib/batch02_evidence_retention.py"
    ).read_text(encoding="utf-8")
    assert "force_push" not in source
    assert "--force-with-lease" in source
    assert "push --force" not in source


def test_source_tree_still_validates():
    validate_batch02_source_tree(
        Path("/workspace/scripts/research"),
        repo_root=Path("/workspace"),
    )


def _patch_large_thresholds(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(retention, "SAFE_SINGLE_BLOB_THRESHOLD_BYTES", 32)
    monkeypatch.setattr(retention, "RAW_CHUNK_SIZE_BYTES", 16)


def _advance_recovery_checkout(repo: Path) -> tuple[str, str]:
    (repo / "tracked.txt").write_text("recovery-infrastructure\n", encoding="utf-8")
    _git(repo, "add", "tracked.txt")
    _commit(repo, "recovery-infrastructure")
    return _git(repo, "rev-parse", "HEAD"), _git(repo, "rev-parse", "HEAD^{tree}")


def _process_loss_ready(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch | None = None,
    *,
    payload: bytes = b"SYNTHETIC-LARGE-ARTIFACT-BYTES",
):
    if monkeypatch is not None:
        _patch_large_thresholds(monkeypatch)
    repo, bare, reservation, ctx = _claimed_run(tmp_path)
    result_path, persisted, source = _persist_payload(repo, ctx, payload)
    claim = ctx._outcome_claim
    exec_sha = reservation.code_sha
    exec_tree = reservation.code_tree
    kwargs = {
        "repo_root": repo,
        "hypothesis_id": reservation.hypothesis_id,
        "stage": reservation.stage,
        "dataset_id": reservation.dataset_id,
        "snapshot_id": reservation.snapshot_id,
        "execution_code_sha": exec_sha,
        "execution_code_tree": exec_tree,
        "evidence_ref": reservation.evidence_ref,
        "expected_reservation_commit_sha": reservation.evidence_head_sha,
        "expected_claim_commit_sha": claim.claim_head_sha,
        "expected_artifact_sha256": persisted.artifact_sha256,
        "expected_artifact_size_bytes": persisted.artifact_size_bytes,
        "local_artifact_path": result_path,
        "run_identity_sha256": persisted.run_identity_sha256,
        "start_inclusive_ms": reservation.start_inclusive_ms,
        "end_exclusive_ms": reservation.end_exclusive_ms,
        "allowed_years": reservation.allowed_years,
        "required_gate_names": reservation.required_gate_names,
        "seeds": dict(reservation.seeds),
        "test_bare_remote": bare,
    }
    del reservation
    del ctx
    del persisted
    del claim
    rec_sha, rec_tree = _advance_recovery_checkout(repo)
    kwargs["recovery_code_sha"] = rec_sha
    kwargs["recovery_code_tree"] = rec_tree
    clear_batch02_retention_runtime_state()
    assert retention._BOUND_RESERVATIONS == {}
    assert retention._BOUND_CLAIMS == {}
    assert retention._BOUND_PERSISTED == {}
    assert retention._BACKEND_BY_ID == {}
    return kwargs, repo, bare, result_path, source, exec_sha, exec_tree, rec_sha, rec_tree


def test_fresh_process_recovery_archives_after_minted_objects_are_gone(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    kwargs, repo, bare, result_path, source, exec_sha, exec_tree, rec_sha, rec_tree = (
        _process_loss_ready(tmp_path, monkeypatch)
    )
    assert exec_sha != rec_sha
    assert exec_tree != rec_tree
    with pytest.raises(CodeIdentityError):
        verify_git_freeze(repo, exec_sha)
    receipt = recover_claimed_batch02_artifact(**kwargs)
    payload = receipt.receipt_payload
    assert payload["execution_code_sha"] == exec_sha
    assert payload["execution_code_tree"] == exec_tree
    assert payload["recovery_code_sha"] == rec_sha
    assert payload["recovery_code_tree"] == rec_tree
    assert payload["recovery_code_sha"] != payload["execution_code_sha"]
    assert payload["archive_representation"] == ARCHIVE_REPRESENTATION_RAW_CHUNKS
    assert payload["reservation_commit_sha"] == kwargs["expected_reservation_commit_sha"]
    assert payload["claim_commit_sha"] == kwargs["expected_claim_commit_sha"]
    assert payload["artifact_sha256"] == kwargs["expected_artifact_sha256"]
    assert payload["artifact_size_bytes"] == kwargs["expected_artifact_size_bytes"]
    assert payload["chunk_size_bytes"] == 16
    assert _hex64(payload["manifest_sha256"])
    manifest_path = chunked_manifest_relpath(
        kwargs["hypothesis_id"], exec_sha, kwargs["expected_artifact_sha256"]
    )
    assert receipt.evidence_path == manifest_path
    assert receipt.code_sha == exec_sha
    assert receipt.code_tree == exec_tree
    names = set(_remote_tree(bare, kwargs["evidence_ref"]))
    assert manifest_path in names
    manifest = json.loads(_remote_blob(bare, kwargs["evidence_ref"], manifest_path))
    blobs = {
        entry["path"]: _remote_blob(bare, kwargs["evidence_ref"], entry["path"])
        for entry in manifest["chunks"]
    }
    reconstructed = reconstruct_raw_chunks(manifest, blobs)
    assert reconstructed == source
    assert sha256_bytes(reconstructed) == kwargs["expected_artifact_sha256"]
    assert len(reconstructed) == kwargs["expected_artifact_size_bytes"]
    parent = subprocess.run(
        ["git", "--git-dir", str(bare), "rev-parse", f"{kwargs['evidence_ref']}^"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip().lower()
    assert parent == kwargs["expected_claim_commit_sha"]
    assert classify_evidence_tree(_remote_tree(bare, kwargs["evidence_ref"])) == STATE_ARCHIVED
    assert result_path.read_bytes() == source
    assert result_path.read_bytes() == reconstructed


def test_fresh_process_recovery_keeps_v1_single_blob(tmp_path: Path):
    kwargs, _repo, bare, result_path, source, exec_sha, _exec_tree, rec_sha, _rec_tree = (
        _process_loss_ready(tmp_path, payload=b"tiny")
    )
    assert uses_raw_chunk_archive(len(source)) is False
    receipt = recover_claimed_batch02_artifact(**kwargs)
    expected = artifact_relpath(
        kwargs["hypothesis_id"], exec_sha, kwargs["expected_artifact_sha256"]
    )
    assert receipt.evidence_path == expected
    assert receipt.receipt_payload["archive_representation"] == ARCHIVE_REPRESENTATION_SINGLE_BLOB
    assert receipt.receipt_payload["recovery_code_sha"] == rec_sha
    assert receipt.receipt_payload["execution_code_sha"] == exec_sha
    assert _remote_blob(bare, kwargs["evidence_ref"], expected) == source
    assert result_path.read_bytes() == source


def test_recovery_fails_when_remote_head_is_not_expected_claim(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    kwargs, _repo, bare, result_path, source, _exec_sha, _exec_tree, _rec_sha, _rec_tree = (
        _process_loss_ready(tmp_path, monkeypatch)
    )
    work = tmp_path / "drift"
    _checkout_evidence(bare, work, kwargs["evidence_ref"])
    (work / "extra.txt").write_text("unknown intermediate\n", encoding="utf-8")
    _git(work, "add", "extra.txt")
    _commit(work, "unknown-intermediate")
    _git(work, "push", "origin", f"HEAD:{kwargs['evidence_ref']}")
    with pytest.raises(PostOutcomeRetentionFailure, match=POST_OUTCOME_STATE):
        recover_claimed_batch02_artifact(**kwargs)
    assert result_path.read_bytes() == source
    assert "receipt.json" not in set(_remote_tree(bare, kwargs["evidence_ref"]))


def test_recovery_fails_when_claim_parent_is_wrong(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    kwargs, _repo, _bare, result_path, source, _e, _t, _r, _rt = _process_loss_ready(
        tmp_path, monkeypatch
    )
    kwargs["expected_reservation_commit_sha"] = kwargs["expected_claim_commit_sha"]
    with pytest.raises(PostOutcomeRetentionFailure, match=POST_OUTCOME_STATE):
        recover_claimed_batch02_artifact(**kwargs)
    assert result_path.read_bytes() == source


def test_recovery_fails_when_reservation_identity_does_not_match_remote(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    kwargs, _repo, _bare, result_path, source, _e, _t, _r, _rt = _process_loss_ready(
        tmp_path, monkeypatch
    )
    kwargs["seeds"] = {"bootstrap": 99}
    with pytest.raises(PostOutcomeRetentionFailure, match=POST_OUTCOME_STATE):
        recover_claimed_batch02_artifact(**kwargs)
    assert result_path.read_bytes() == source


def test_recovery_fails_when_remote_reservation_bytes_are_mutated(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    kwargs, _repo, bare, result_path, source, _e, _t, _r, _rt = _process_loss_ready(
        tmp_path, monkeypatch
    )
    work = tmp_path / "mutated-reservation"
    _checkout_evidence(bare, work, kwargs["evidence_ref"])
    reservation_path = work / "reservation.json"
    mutated = json.loads(reservation_path.read_bytes())
    mutated["seeds"] = {"bootstrap": 99}
    reservation_path.write_bytes(
        json.dumps(mutated, sort_keys=True, separators=(",", ":")).encode("utf-8")
    )
    _git(work, "add", "reservation.json")
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=Retention Test",
            "-c",
            "user.email=retention@example.invalid",
            "commit",
            "--amend",
            "--no-edit",
        ],
        cwd=work,
        check=True,
        capture_output=True,
        text=True,
    )
    new_claim = _git(work, "rev-parse", "HEAD")
    subprocess.run(
        ["git", "--git-dir", str(bare), "update-ref", kwargs["evidence_ref"], new_claim],
        check=True,
        capture_output=True,
        text=True,
    )
    kwargs["expected_claim_commit_sha"] = new_claim
    with pytest.raises(PostOutcomeRetentionFailure, match=POST_OUTCOME_STATE):
        recover_claimed_batch02_artifact(**kwargs)
    assert result_path.read_bytes() == source
    assert "receipt.json" not in set(_remote_tree(bare, kwargs["evidence_ref"]))


def test_recovery_fails_when_claim_identity_does_not_match_remote(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    kwargs, _repo, bare, result_path, source, _e, _t, _r, _rt = _process_loss_ready(
        tmp_path, monkeypatch
    )
    work = tmp_path / "mutated-claim"
    _checkout_evidence(bare, work, kwargs["evidence_ref"])
    claim_path = work / "outcome_claim.json"
    mutated = json.loads(claim_path.read_text(encoding="utf-8"))
    mutated["seeds"] = {"bootstrap": 99}
    claim_path.write_bytes(
        json.dumps(mutated, sort_keys=True, separators=(",", ":")).encode("utf-8")
    )
    _git(work, "add", "outcome_claim.json")
    import subprocess

    subprocess.run(
        [
            "git",
            "-c",
            "user.name=Retention Test",
            "-c",
            "user.email=retention@example.invalid",
            "commit",
            "--amend",
            "--no-edit",
        ],
        cwd=work,
        check=True,
        capture_output=True,
        text=True,
    )
    new_claim = _git(work, "rev-parse", "HEAD")
    subprocess.run(
        ["git", "--git-dir", str(bare), "update-ref", kwargs["evidence_ref"], new_claim],
        check=True,
        capture_output=True,
        text=True,
    )
    kwargs["expected_claim_commit_sha"] = new_claim
    with pytest.raises(PostOutcomeRetentionFailure, match=POST_OUTCOME_STATE):
        recover_claimed_batch02_artifact(**kwargs)
    assert result_path.read_bytes() == source
    assert "receipt.json" not in set(_remote_tree(bare, kwargs["evidence_ref"]))


def test_recovery_fails_when_local_artifact_digest_or_size_differs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    kwargs, _repo, bare, result_path, source, _e, _t, _r, _rt = _process_loss_ready(
        tmp_path, monkeypatch
    )
    result_path.write_bytes(source + b"X")
    with pytest.raises(PostOutcomeRetentionFailure, match=POST_OUTCOME_STATE):
        recover_claimed_batch02_artifact(**kwargs)
    kwargs["local_artifact_path"] = result_path
    result_path.write_bytes(source)
    kwargs["expected_artifact_size_bytes"] = len(source) + 1
    with pytest.raises(PostOutcomeRetentionFailure, match=POST_OUTCOME_STATE):
        recover_claimed_batch02_artifact(**kwargs)
    assert result_path.read_bytes() == source
    assert "receipt.json" not in set(_remote_tree(bare, kwargs["evidence_ref"]))


def test_recovery_fails_when_execution_tree_differs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    kwargs, _repo, _bare, result_path, source, _e, _t, _r, rec_tree = _process_loss_ready(
        tmp_path, monkeypatch
    )
    kwargs["execution_code_tree"] = rec_tree
    with pytest.raises(PostOutcomeRetentionFailure, match=POST_OUTCOME_STATE):
        recover_claimed_batch02_artifact(**kwargs)
    assert result_path.read_bytes() == source


def test_recovery_fails_when_recovery_checkout_is_dirty(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    kwargs, repo, _bare, result_path, source, _e, _t, _r, _rt = _process_loss_ready(
        tmp_path, monkeypatch
    )
    (repo / "tracked.txt").write_text("dirty recovery checkout\n", encoding="utf-8")
    with pytest.raises(PostOutcomeRetentionFailure, match=POST_OUTCOME_STATE):
        recover_claimed_batch02_artifact(**kwargs)
    assert result_path.read_bytes() == source


def test_recovery_fails_when_one_remote_chunk_is_mutated(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    kwargs, _repo, bare, result_path, source, _e, _t, _r, _rt = _process_loss_ready(
        tmp_path, monkeypatch
    )
    original = retention._show_blob

    def tainted(isolated, commit, path):
        data = original(isolated, commit, path)
        if str(path).endswith("/chunks/00000.part"):
            return data[:-1] + (b"X" if data[-1:] != b"X" else b"Y")
        return data

    monkeypatch.setattr(retention, "_show_blob", tainted)
    with pytest.raises(PostOutcomeRetentionFailure, match=POST_OUTCOME_STATE):
        recover_claimed_batch02_artifact(**kwargs)
    assert result_path.read_bytes() == source


def test_recovery_fails_when_one_remote_chunk_is_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    kwargs, _repo, _bare, result_path, source, _e, _t, _r, _rt = _process_loss_ready(
        tmp_path, monkeypatch
    )
    original = retention._tree_names

    def missing(isolated, commit):
        names = list(original(isolated, commit))
        if any(name.endswith("manifest.json") for name in names):
            parts = [name for name in names if name.endswith(".part")]
            names.remove(parts[-1])
        return names

    monkeypatch.setattr(retention, "_tree_names", missing)
    with pytest.raises(PostOutcomeRetentionFailure, match=POST_OUTCOME_STATE):
        recover_claimed_batch02_artifact(**kwargs)
    assert result_path.read_bytes() == source


def test_recovery_fails_when_extra_remote_chunk_exists(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    kwargs, _repo, _bare, result_path, source, _e, _t, _r, _rt = _process_loss_ready(
        tmp_path, monkeypatch
    )
    original = retention._tree_names

    def extra(isolated, commit):
        names = list(original(isolated, commit))
        parts = [name for name in names if name.endswith(".part")]
        if any(name.endswith("manifest.json") for name in names) and parts:
            prefix = parts[0].rsplit("/", 1)[0]
            names.append(f"{prefix}/{len(parts):05d}.part")
        return names

    monkeypatch.setattr(retention, "_tree_names", extra)
    with pytest.raises(PostOutcomeRetentionFailure, match=POST_OUTCOME_STATE):
        recover_claimed_batch02_artifact(**kwargs)
    assert result_path.read_bytes() == source


def test_recovery_fails_when_manifest_is_reordered(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    kwargs, _repo, _bare, result_path, source, _e, _t, _r, _rt = _process_loss_ready(
        tmp_path, monkeypatch
    )
    original = retention._show_blob

    def reordered(isolated, commit, path):
        data = original(isolated, commit, path)
        if str(path).endswith("manifest.json"):
            payload = json.loads(data.decode("utf-8"))
            payload["chunks"] = list(reversed(list(payload["chunks"])))
            return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode(
                "utf-8"
            ) + b"\n"
        return data

    monkeypatch.setattr(retention, "_show_blob", reordered)
    with pytest.raises(PostOutcomeRetentionFailure, match=POST_OUTCOME_STATE):
        recover_claimed_batch02_artifact(**kwargs)
    assert result_path.read_bytes() == source


def test_recovery_fails_when_push_would_not_be_fast_forward(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    kwargs, _repo, bare, result_path, source, _e, _t, _r, _rt = _process_loss_ready(
        tmp_path, monkeypatch
    )
    original = retention._ls_remote_sha
    calls = {"n": 0}

    def drifted(isolated, endpoint, evidence_ref):
        calls["n"] += 1
        sha = original(isolated, endpoint, evidence_ref)
        if calls["n"] >= 3:
            return "d" * 40
        return sha

    monkeypatch.setattr(retention, "_ls_remote_sha", drifted)
    with pytest.raises(PostOutcomeRetentionFailure, match=POST_OUTCOME_STATE):
        recover_claimed_batch02_artifact(**kwargs)
    assert result_path.read_bytes() == source
    assert classify_evidence_tree(_remote_tree(bare, kwargs["evidence_ref"])) == STATE_CLAIMED
    assert "receipt.json" not in set(_remote_tree(bare, kwargs["evidence_ref"]))


def test_recovery_api_is_exported_and_not_a_runner_call():
    from scripts.research.lib import batch02_contracts
    from scripts.research.lib.batch02_source_policy import (
        _CANONICAL_PUBLIC_API,
        _RETENTION_RUNNER_CALLS,
    )

    assert hasattr(batch02_contracts, "recover_claimed_batch02_artifact")
    assert "recover_claimed_batch02_artifact" in _CANONICAL_PUBLIC_API
    assert "recover_claimed_batch02_artifact" not in _RETENTION_RUNNER_CALLS
