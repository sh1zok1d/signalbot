"""Hypothesis-neutral ingest, reconnect/gap, and backfill labeling."""

from __future__ import annotations

import json
import os
import uuid
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from scripts.research.forward_market_observability_v1.clock import (
    ClockWatch,
    ReceiptStamp,
    capture_receipt,
)
from scripts.research.forward_market_observability_v1.envelope import (
    attach_parse_metadata,
    build_raw_envelope,
    sha256_bytes,
)
from scripts.research.forward_market_observability_v1.parse import (
    build_parsed_derivative,
    parse_native_fields,
)
from scripts.research.forward_market_observability_v1.schemas import (
    EVENT_DISCONNECT,
    EVENT_GAP,
    EVENT_PARSE_ERROR,
    EVENT_RECONNECT,
    EVENT_SCHEMA,
    SOURCE_TYPE_BACKFILL,
    SOURCE_TYPE_LIVE,
    assert_no_scientific_fields,
    classify_source_observation_validity,
)
from scripts.research.forward_market_observability_v1.storage import (
    ChunkStore,
    atomic_write_json,
    fsync_dir,
)
from scripts.research.forward_market_observability_v1.transport import TransportReceipt


class CollectorError(RuntimeError):
    """Acquisition refused an unsafe operation."""


class SourceRuntime:
    def __init__(
        self,
        *,
        session_id: str,
        session_dir: Path,
        source: Mapping[str, Any],
        max_messages: int,
        max_bytes: int,
        clock_watch: ClockWatch | None = None,
        stamp_fn: Callable[[], ReceiptStamp] = capture_receipt,
        parser: Callable[[bytes], Mapping[str, Any]] = parse_native_fields,
    ) -> None:
        self.session_id = session_id
        self.session_dir = session_dir
        self.source = dict(source)
        self.source_id = str(source["source_id"])
        self.instrument = str(source.get("instrument") or "BTCUSDT")
        self.store = ChunkStore(
            session_dir=session_dir,
            session_id=session_id,
            source_id=self.source_id,
            max_messages=max_messages,
            max_bytes=max_bytes,
        )
        self.clock_watch = clock_watch or ClockWatch()
        self.stamp_fn = stamp_fn
        self.parser = parser
        self.connection_id = str(uuid.uuid4())
        self.message_count = 0
        self.parse_error_count = 0
        self.checksum_failure_count = 0
        self.invalid_observation_count = 0
        self.reconnect_count = 0
        self.seen_hashes: dict[str, int] = {}
        self.last_durable_receipt_utc: str | None = None
        self.last_durable_monotonic_ns: int | None = None
        self._pending_gap: dict[str, str | None] | None = None
        self.events_path = session_dir / "events" / f"{self.source_id}.jsonl"
        self.parsed_path = session_dir / "parsed" / f"{self.source_id}.jsonl"
        self.events_path.parent.mkdir(parents=True, exist_ok=True)
        self.parsed_path.parent.mkdir(parents=True, exist_ok=True)
        self._health = {
            "message_count": 0,
            "bytes_received": 0,
            "reconnect_count": 0,
            "parse_error_count": 0,
            "checksum_failures": 0,
            "invalid_observation_count": 0,
            "clock_anomalies": 0,
            "coverage_gaps": 0,
            "chunk_count": 0,
            "last_receipt_age_s": None,
        }

    def ingest(
        self,
        receipt: TransportReceipt,
        *,
        source_type: str = SOURCE_TYPE_LIVE,
        parser_hook: Callable[[], None] | None = None,
    ) -> dict[str, Any]:
        if source_type not in {SOURCE_TYPE_LIVE, SOURCE_TYPE_BACKFILL}:
            raise CollectorError(f"UNKNOWN_SOURCE_TYPE:{source_type}")
        if source_type == SOURCE_TYPE_BACKFILL:
            # legal_available_at remains the later local receipt, not historical event time.
            pass
        stamp = self.stamp_fn()
        anomaly = self.clock_watch.observe(stamp)
        if anomaly is not None:
            self._health["clock_anomalies"] += 1
            self._append_event(anomaly)
        envelope = build_raw_envelope(
            session_id=self.session_id,
            source_id=self.source_id,
            instrument=self.instrument,
            stamp=stamp,
            raw_payload=receipt.raw_payload,
            transport=receipt.transport,
            connection_id=self.connection_id,
            source_type=source_type,
            message_index=self.message_count,
        )
        if sha256_bytes(receipt.raw_payload) != envelope["raw_payload_sha256"]:
            self.checksum_failure_count += 1
            self._health["checksum_failures"] += 1
            raise CollectorError("RAW_SHA256_MISMATCH")
        parse_error = None
        native: dict[str, Any] | None = None
        if parser_hook is not None:
            parser_hook()
        try:
            native = dict(self.parser(receipt.raw_payload))
        except Exception as exc:  # noqa: BLE001 — preserve raw evidence on parse failure
            parse_error = f"{type(exc).__name__}:{exc}"
            self.parse_error_count += 1
            self._health["parse_error_count"] += 1
            self._append_event(
                {
                    "event_type": EVENT_PARSE_ERROR,
                    "error": parse_error,
                    "raw_payload_sha256": envelope["raw_payload_sha256"],
                }
            )
        source_observation_valid = classify_source_observation_validity(
            self.source_id,
            transport=receipt.transport,
            native=native,
            parse_error=parse_error,
        )
        if not source_observation_valid:
            self.invalid_observation_count += 1
            self._health["invalid_observation_count"] = self.invalid_observation_count
        envelope = attach_parse_metadata(
            envelope,
            exchange_event_time=None if native is None else native.get("exchange_event_time"),
            exchange_sequence=None if native is None else native.get("exchange_sequence"),
            parse_error=parse_error,
            source_observation_valid=source_observation_valid,
        )
        digest = envelope["raw_payload_sha256"]
        duplicate = digest in self.seen_hashes
        self.seen_hashes[digest] = self.seen_hashes.get(digest, 0) + 1
        chunk_info = self.store.append_envelope(envelope)
        chunk_id = None
        if chunk_info.get("status") == "COMPLETE":
            chunk_id = chunk_info.get("chunk_id")
            self._health["chunk_count"] = len(self.store.completed_chunks)
        elif self.store._open is not None:
            chunk_id = f"chunk-{self.store._open.chunk_index:06d}"
        parsed = None
        if native is not None:
            parsed = build_parsed_derivative(
                envelope,
                chunk_id=chunk_id,
                record_index=self.message_count,
                duplicate_candidate=duplicate,
                parser=lambda _raw: native,
            )
            self._append_jsonl(self.parsed_path, parsed)
        self.message_count += 1
        self._health["message_count"] = self.message_count
        self._health["bytes_received"] += envelope["raw_payload_length"]
        self.last_durable_receipt_utc = envelope["local_received_at_utc"]
        self.last_durable_monotonic_ns = envelope["local_received_monotonic_ns"]
        if self._pending_gap is not None:
            pending = self._pending_gap
            self._pending_gap = None
            self.record_gap(
                last_before_utc=pending.get("last_before_utc"),
                first_after_utc=envelope["local_received_at_utc"],
                disconnect_utc=pending.get("disconnect_utc"),
                reconnect_utc=pending.get("reconnect_utc"),
            )
        return {
            "envelope": envelope,
            "parsed": parsed,
            "chunk": chunk_info,
            "duplicate_candidate": duplicate,
        }

    def ingest_backfill(self, receipt: TransportReceipt) -> dict[str, Any]:
        result = self.ingest(receipt, source_type=SOURCE_TYPE_BACKFILL)
        if result["envelope"]["source_type"] != SOURCE_TYPE_BACKFILL:
            raise CollectorError("BACKFILL_NOT_LABELED")
        if result["envelope"].get("original_live_receipt") is not False:
            raise CollectorError("BACKFILL_MASQUERADED_AS_LIVE")
        if result["envelope"]["legal_available_at"] != result["envelope"]["local_received_at_utc"]:
            raise CollectorError("BACKFILL_LEGAL_AVAILABLE_AT_MUST_BE_LOCAL_RECEIPT")
        return result

    def disconnect(self, *, utc: str) -> None:
        self._append_event(
            {
                "event_type": EVENT_DISCONNECT,
                "connection_id": self.connection_id,
                "disconnect_utc": utc,
                "last_durable_receipt_utc": self.last_durable_receipt_utc,
            }
        )

    def reconnect(self, *, disconnect_utc: str, reconnect_utc: str) -> str:
        previous = self.connection_id
        last_before = self.last_durable_receipt_utc
        self.disconnect(utc=disconnect_utc)
        self.connection_id = str(uuid.uuid4())
        self.reconnect_count += 1
        self._health["reconnect_count"] = self.reconnect_count
        self._pending_gap = {
            "disconnect_utc": disconnect_utc,
            "reconnect_utc": reconnect_utc,
            "last_before_utc": last_before,
        }
        self._append_event(
            {
                "event_type": EVENT_RECONNECT,
                "previous_connection_id": previous,
                "connection_id": self.connection_id,
                "disconnect_utc": disconnect_utc,
                "reconnect_utc": reconnect_utc,
                "last_durable_receipt_before_disconnect": last_before,
            }
        )
        return self.connection_id

    def record_gap(
        self,
        *,
        last_before_utc: str | None,
        first_after_utc: str,
        disconnect_utc: str | None = None,
        reconnect_utc: str | None = None,
    ) -> None:
        self._health["coverage_gaps"] += 1
        self._append_event(
            {
                "event_type": EVENT_GAP,
                "connection_id": self.connection_id,
                "disconnect_utc": disconnect_utc,
                "reconnect_utc": reconnect_utc,
                "last_durable_receipt_before_disconnect": last_before_utc,
                "first_durable_receipt_after_reconnect": first_after_utc,
                "filled_with_exchange_event_time": False,
                "labeled_as_original_point_in_time_receipt": False,
            }
        )

    def finalize(self, *, reason: str = "SESSION_STOP") -> None:
        if self.store._open is not None:
            if self.store._open.message_count > 0:
                self.store.finalize_open_chunk()
            else:
                self.store.close_incomplete(reason=reason)
        self._health["chunk_count"] = len(self.store.completed_chunks)
        atomic_write_json(
            self.session_dir / "health" / f"{self.source_id}.json",
            {
                "schema_version": "forward_market_observability_v1_health/1.0.0",
                "source_id": self.source_id,
                "operational_metrics_only": True,
                **self._health,
            },
        )

    def _append_event(self, event: Mapping[str, Any]) -> None:
        payload = {"schema_version": EVENT_SCHEMA, **event}
        assert_no_scientific_fields(payload, where="event")
        self._append_jsonl(self.events_path, payload)

    def _append_jsonl(self, path: Path, payload: Mapping[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8") + b"\n"
        with open(path, "ab") as handle:
            handle.write(line)
            handle.flush()
            os.fsync(handle.fileno())
        fsync_dir(path.parent)
