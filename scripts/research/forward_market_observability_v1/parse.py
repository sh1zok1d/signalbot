"""Rebuildable parsed derivatives. Never the root evidence."""

from __future__ import annotations

import json
import hashlib
from typing import Any, Callable, Mapping

from scripts.research.forward_market_observability_v1.envelope import decode_raw_payload
from scripts.research.forward_market_observability_v1.schemas import (
    FORBIDDEN_SCIENTIFIC_FIELDS,
    PARSED_DERIVATIVE_SCHEMA,
    CollectorSchemaError,
    assert_no_scientific_fields,
)


def parse_native_fields(raw_payload: bytes) -> dict[str, Any]:
    """Extract native exchange fields only. No predictive quantities."""
    text = raw_payload.decode("utf-8")
    payload = json.loads(text)
    if not isinstance(payload, dict):
        raise CollectorSchemaError("PARSED_PAYLOAD_NOT_OBJECT")
    overlap = set(payload) & FORBIDDEN_SCIENTIFIC_FIELDS
    if overlap:
        raise CollectorSchemaError(f"SCIENTIFIC_FIELD_IN_EXCHANGE_PAYLOAD:{sorted(overlap)}")
    parsed: dict[str, Any] = {
        "symbol": payload.get("s") or payload.get("symbol"),
        "event_type": payload.get("e"),
        "exchange_event_time": payload.get("E") or payload.get("time"),
        "exchange_sequence": payload.get("u") or payload.get("seq"),
        "mark_price": payload.get("p") or payload.get("markPrice"),
        "index_price": payload.get("i") or payload.get("indexPrice"),
        "estimated_settle_price": payload.get("P") or payload.get("estimatedSettlePrice"),
        "funding_rate": payload.get("r") or payload.get("lastFundingRate"),
        "next_funding_time": payload.get("T") or payload.get("nextFundingTime"),
        "interest_rate": payload.get("interestRate"),
        "open_interest": payload.get("openInterest"),
        "premium_index": payload.get("premiumIndex"),
    }
    return parsed


def build_parsed_derivative(
    envelope: Mapping[str, Any],
    *,
    chunk_id: str | None,
    record_index: int,
    byte_offset: int | None = None,
    duplicate_candidate: bool = False,
    parser: Callable[[bytes], Mapping[str, Any]] = parse_native_fields,
) -> dict[str, Any]:
    raw = decode_raw_payload(str(envelope["raw_payload"]))
    if envelope["raw_payload_sha256"] != hashlib.sha256(raw).hexdigest():
        raise CollectorSchemaError("PARSED_RAW_SHA256_MISMATCH")
    native = dict(parser(raw))
    derivative = {
        "schema_version": PARSED_DERIVATIVE_SCHEMA,
        "session_id": envelope["session_id"],
        "source_id": envelope["source_id"],
        "instrument": envelope["instrument"],
        "chunk_id": chunk_id,
        "record_index": record_index,
        "byte_offset": byte_offset,
        "raw_payload_sha256": envelope["raw_payload_sha256"],
        "local_received_at_utc": envelope["local_received_at_utc"],
        "legal_available_at": envelope["legal_available_at"],
        "duplicate_candidate": duplicate_candidate,
        "root_evidence": "raw_envelope",
        "native_fields": native,
    }
    assert_no_scientific_fields(derivative, where="parsed_derivative")
    return derivative
