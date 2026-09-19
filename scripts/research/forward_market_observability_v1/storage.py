"""Append-only durable chunk storage."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from scripts.research.forward_market_observability_v1.envelope import sha256_bytes
from scripts.research.forward_market_observability_v1.schemas import (
    CHUNK_SCHEMA,
    CHUNK_STATUS_COMPLETE,
    CHUNK_STATUS_INCOMPLETE,
    CHUNK_STATUS_QUARANTINED,
    MANIFEST_SCHEMA,
    assert_no_scientific_fields,
)


class StorageError(RuntimeError):
    """Durable storage refused an unsafe operation."""


def fsync_dir(path: Path) -> None:
    fd = os.open(str(path), os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def atomic_write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "wb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, path)
    fsync_dir(path.parent)


def atomic_write_json(path: Path, payload: Mapping[str, Any]) -> None:
    assert_no_scientific_fields(payload, where=str(path))
    data = json.dumps(payload, sort_keys=True, indent=2).encode("utf-8") + b"\n"
    atomic_write_bytes(path, data)


def _chunk_stem(chunk_index: int) -> str:
    return f"chunk-{chunk_index:06d}"


@dataclass
class OpenChunk:
    chunk_index: int
    session_id: str
    source_id: str
    path: Path
    handle: Any
    message_count: int = 0
    byte_size: int = 0
    first_local_received_at_utc: str | None = None
    last_local_received_at_utc: str | None = None
    first_monotonic_ns: int | None = None
    last_monotonic_ns: int | None = None
    status: str = CHUNK_STATUS_INCOMPLETE


@dataclass
class ChunkStore:
    session_dir: Path
    session_id: str
    source_id: str
    max_messages: int = 100
    max_bytes: int = 1_048_576
    _open: OpenChunk | None = None
    _completed: list[dict[str, Any]] = field(default_factory=list)
    _next_index: int = 1

    def __post_init__(self) -> None:
        self.raw_dir = self.session_dir / "raw" / self.source_id
        self.manifest_dir = self.session_dir / "manifests"
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.manifest_dir.mkdir(parents=True, exist_ok=True)
        existing = sorted(self.raw_dir.glob("chunk-*.jsonl"))
        if existing:
            last = existing[-1].name
            self._next_index = int(last.split("-")[1].split(".")[0]) + 1
            for path in existing:
                meta_path = path.with_suffix(".meta.json")
                if meta_path.is_file():
                    meta = json.loads(meta_path.read_text(encoding="utf-8"))
                    self._completed.append(meta)

    def append_envelope(self, envelope: Mapping[str, Any]) -> dict[str, Any]:
        assert_no_scientific_fields(envelope, where="chunk_append")
        line = json.dumps(envelope, sort_keys=True, separators=(",", ":")).encode("utf-8") + b"\n"
        chunk = self._ensure_open()
        chunk.handle.write(line)
        chunk.handle.flush()
        os.fsync(chunk.handle.fileno())
        chunk.message_count += 1
        chunk.byte_size += len(line)
        utc = str(envelope["local_received_at_utc"])
        mono = int(envelope["local_received_monotonic_ns"])
        if chunk.first_local_received_at_utc is None:
            chunk.first_local_received_at_utc = utc
            chunk.first_monotonic_ns = mono
        chunk.last_local_received_at_utc = utc
        chunk.last_monotonic_ns = mono
        if chunk.message_count >= self.max_messages or chunk.byte_size >= self.max_bytes:
            return self.finalize_open_chunk()
        return {"status": CHUNK_STATUS_INCOMPLETE, "chunk_index": chunk.chunk_index}

    def finalize_open_chunk(self) -> dict[str, Any]:
        chunk = self._open
        if chunk is None:
            raise StorageError("NO_OPEN_CHUNK")
        os.fsync(chunk.handle.fileno())
        chunk.handle.close()
        final_path = self.raw_dir / f"{_chunk_stem(chunk.chunk_index)}.jsonl"
        if final_path.exists():
            raise StorageError(f"CHUNK_ALREADY_EXISTS:{final_path}")
        os.replace(chunk.path, final_path)
        fsync_dir(self.raw_dir)
        exact = final_path.read_bytes()
        digest = sha256_bytes(exact)
        meta = {
            "schema_version": CHUNK_SCHEMA,
            "chunk_id": _chunk_stem(chunk.chunk_index),
            "chunk_index": chunk.chunk_index,
            "session_id": chunk.session_id,
            "source_id": chunk.source_id,
            "message_count": chunk.message_count,
            "first_local_received_at_utc": chunk.first_local_received_at_utc,
            "last_local_received_at_utc": chunk.last_local_received_at_utc,
            "first_monotonic_ns": chunk.first_monotonic_ns,
            "last_monotonic_ns": chunk.last_monotonic_ns,
            "byte_size": len(exact),
            "sha256": digest,
            "status": CHUNK_STATUS_COMPLETE,
            "path": str(final_path.relative_to(self.session_dir)),
        }
        assert_no_scientific_fields(meta, where="chunk_meta")
        atomic_write_json(final_path.with_suffix(".meta.json"), meta)
        self._completed.append(meta)
        self._open = None
        self._write_manifest()
        return meta

    def close_incomplete(self, *, reason: str) -> dict[str, Any] | None:
        chunk = self._open
        if chunk is None:
            return None
        try:
            chunk.handle.flush()
            os.fsync(chunk.handle.fileno())
        finally:
            chunk.handle.close()
        incomplete = {
            "schema_version": CHUNK_SCHEMA,
            "chunk_id": _chunk_stem(chunk.chunk_index),
            "chunk_index": chunk.chunk_index,
            "session_id": chunk.session_id,
            "source_id": chunk.source_id,
            "message_count": chunk.message_count,
            "first_local_received_at_utc": chunk.first_local_received_at_utc,
            "last_local_received_at_utc": chunk.last_local_received_at_utc,
            "first_monotonic_ns": chunk.first_monotonic_ns,
            "last_monotonic_ns": chunk.last_monotonic_ns,
            "byte_size": chunk.byte_size,
            "status": CHUNK_STATUS_INCOMPLETE,
            "reason": reason,
            "path": str(chunk.path.relative_to(self.session_dir)),
        }
        atomic_write_json(chunk.path.with_suffix(".incomplete.json"), incomplete)
        self._open = None
        return incomplete

    def _ensure_open(self) -> OpenChunk:
        if self._open is not None:
            return self._open
        index = self._next_index
        self._next_index += 1
        partial = self.raw_dir / f"{_chunk_stem(index)}.jsonl.partial"
        if (self.raw_dir / f"{_chunk_stem(index)}.jsonl").exists():
            raise StorageError(f"CHUNK_ALREADY_EXISTS:{index}")
        handle = open(partial, "ab")
        self._open = OpenChunk(
            chunk_index=index,
            session_id=self.session_id,
            source_id=self.source_id,
            path=partial,
            handle=handle,
        )
        return self._open

    def _write_manifest(self) -> None:
        payload = {
            "schema_version": MANIFEST_SCHEMA,
            "session_id": self.session_id,
            "source_id": self.source_id,
            "chunk_count": len(self._completed),
            "chunks": [
                {
                    "chunk_id": item["chunk_id"],
                    "chunk_index": item["chunk_index"],
                    "sha256": item["sha256"],
                    "status": item["status"],
                    "message_count": item["message_count"],
                    "path": item["path"],
                }
                for item in self._completed
            ],
        }
        ordered = [item["chunk_index"] for item in self._completed]
        if ordered != sorted(ordered) or ordered != list(range(1, len(ordered) + 1)):
            raise StorageError(f"MANIFEST_ORDER_INVALID:{ordered}")
        atomic_write_json(self.manifest_dir / f"{self.source_id}.json", payload)

    @property
    def completed_chunks(self) -> list[dict[str, Any]]:
        return list(self._completed)


def quarantine_leftover_partials(session_dir: Path) -> list[dict[str, Any]]:
    """Mark leftover .partial files INCOMPLETE. Never complete them in place."""
    quarantined: list[dict[str, Any]] = []
    raw_root = session_dir / "raw"
    if not raw_root.is_dir():
        return quarantined
    for partial in raw_root.glob("*/*.jsonl.partial"):
        note = {
            "schema_version": CHUNK_SCHEMA,
            "path": str(partial.relative_to(session_dir)),
            "status": CHUNK_STATUS_QUARANTINED,
            "reason": "LEFTOVER_PARTIAL_NOT_COMPLETED_IN_PLACE",
        }
        atomic_write_json(partial.with_suffix(".quarantined.json"), note)
        quarantined.append(note)
    return quarantined


def verify_chunk_sha256(chunk_path: Path, expected: str) -> bool:
    return sha256_bytes(chunk_path.read_bytes()) == expected
