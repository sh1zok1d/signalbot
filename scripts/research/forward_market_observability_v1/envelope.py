"""Raw-record envelope. Receipt stamps are assigned before parsing."""

from __future__ import annotations

import base64
import hashlib
from typing import Any, Mapping

from scripts.research.forward_market_observability_v1.clock import ReceiptStamp
from scripts.research.forward_market_observability_v1.schemas import (
    LEGAL_AVAILABLE_AT_RULE,
    RAW_ENVELOPE_REQUIRED_FIELDS,
    RAW_ENVELOPE_SCHEMA,
    SOURCE_TYPE_BACKFILL,
    SOURCE_TYPE_LIVE,
    assert_no_scientific_fields,
)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def encode_raw_payload(raw: bytes) -> str:
    return base64.b64encode(raw).decode("ascii")


def decode_raw_payload(encoded: str) -> bytes:
    return base64.b64decode(encoded.encode("ascii"), validate=True)


def build_raw_envelope(
    *,
    session_id: str,
    source_id: str,
    instrument: str,
    stamp: ReceiptStamp,
    raw_payload: bytes,
    transport: Mapping[str, Any],
    connection_id: str,
    source_type: str = SOURCE_TYPE_LIVE,
    message_index: int | None = None,
) -> dict[str, Any]:
    if source_type not in {SOURCE_TYPE_LIVE, SOURCE_TYPE_BACKFILL}:
        raise ValueError(f"UNKNOWN_SOURCE_TYPE:{source_type}")
    if not isinstance(raw_payload, (bytes, bytearray)):
        raise TypeError("RAW_PAYLOAD_MUST_BE_BYTES")
    raw = bytes(raw_payload)
    envelope: dict[str, Any] = {
        "schema_version": RAW_ENVELOPE_SCHEMA,
        "session_id": session_id,
        "source_id": source_id,
        "instrument": instrument,
        "local_received_at_utc": stamp.local_received_at_utc,
        "local_received_monotonic_ns": stamp.local_received_monotonic_ns,
        "legal_available_at": stamp.legal_available_at,
        "legal_available_at_rule": LEGAL_AVAILABLE_AT_RULE,
        "exchange_event_time": None,
        "exchange_sequence": None,
        "raw_payload_length": len(raw),
        "raw_payload_sha256": sha256_bytes(raw),
        "raw_payload_encoding": "base64",
        "raw_payload": encode_raw_payload(raw),
        "transport": dict(transport),
        "connection_id": connection_id,
        "source_type": source_type,
        "message_index": message_index,
        "parse_error": None,
        # Set by attach_parse_metadata once the payload has been classified.
        # Never true before classification: an unclassified observation is
        # never treated as valid market evidence.
        "source_observation_valid": False,
    }
    if source_type == SOURCE_TYPE_BACKFILL:
        envelope["original_live_receipt"] = False
        envelope["backfill_cannot_masquerade_as_original_live_receipt"] = True
    assert_no_scientific_fields(envelope, where="raw_envelope")
    for field in RAW_ENVELOPE_REQUIRED_FIELDS:
        if envelope.get(field) in (None, ""):
            raise ValueError(f"RAW_ENVELOPE_MISSING:{field}")
    return envelope


def attach_parse_metadata(
    envelope: Mapping[str, Any],
    *,
    exchange_event_time: Any = None,
    exchange_sequence: Any = None,
    parse_error: str | None = None,
    source_observation_valid: bool = False,
) -> dict[str, Any]:
    """Add derivative metadata. Must not change raw payload fields."""
    if not isinstance(source_observation_valid, bool):
        raise TypeError("SOURCE_OBSERVATION_VALID_MUST_BE_BOOL")
    updated = dict(envelope)
    raw_before = updated["raw_payload"]
    sha_before = updated["raw_payload_sha256"]
    length_before = updated["raw_payload_length"]
    utc_before = updated["local_received_at_utc"]
    mono_before = updated["local_received_monotonic_ns"]
    legal_before = updated["legal_available_at"]
    updated["exchange_event_time"] = exchange_event_time
    updated["exchange_sequence"] = exchange_sequence
    updated["parse_error"] = parse_error
    updated["source_observation_valid"] = source_observation_valid
    if updated["raw_payload"] != raw_before:
        raise ValueError("RAW_PAYLOAD_MUTATED")
    if updated["raw_payload_sha256"] != sha_before:
        raise ValueError("RAW_SHA256_MUTATED")
    if updated["raw_payload_length"] != length_before:
        raise ValueError("RAW_LENGTH_MUTATED")
    if updated["local_received_at_utc"] != utc_before:
        raise ValueError("RECEIPT_UTC_MUTATED")
    if updated["local_received_monotonic_ns"] != mono_before:
        raise ValueError("RECEIPT_MONOTONIC_MUTATED")
    if updated["legal_available_at"] != legal_before:
        raise ValueError("LEGAL_AVAILABLE_AT_MUTATED")
    if updated["legal_available_at"] != updated["local_received_at_utc"]:
        raise ValueError("LEGAL_AVAILABLE_AT_MUST_EQUAL_LOCAL_RECEIVED_AT_UTC")
    assert_no_scientific_fields(updated, where="raw_envelope_after_parse")
    return updated
