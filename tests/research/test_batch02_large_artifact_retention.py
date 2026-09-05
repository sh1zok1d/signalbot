"""Synthetic tests for Batch02 large-artifact exact-byte archival.

These tests never open CORE_BTC_BINANCE_V0, 2025, 2026, or any real
Batch02 market artifact. Thresholds and chunk sizes are monkeypatched
to tiny values so the chunked path can be exercised with small bytes.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.research.lib.batch02_contracts import (
    archive_batch02_result,
    persist_batch02_retained_result,
    prepare_batch02_retained_run,
)
from scripts.research.lib.batch02_evidence_retention import (
    ARCHIVE_REPRESENTATION_RAW_CHUNKS,
    CHUNKED_ENCODING,
    GITHUB_REGULAR_GIT_OBJECT_LIMIT_BYTES,
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
    reconstruct_raw_chunks,
    sha256_bytes,
    split_raw_bytes,
    uses_raw_chunk_archive,
)
from scripts.research.lib.batch02_source_policy import validate_batch02_source_tree
from tests.research.test_batch02_durable_evidence_retention import (
    _HEX40,
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
