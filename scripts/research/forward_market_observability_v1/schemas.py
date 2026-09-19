"""Frozen schema identities for FORWARD_MARKET_OBSERVABILITY_V1.

Hypothesis-neutral. Scientific outcome fields are forbidden in collector
records.
"""

from __future__ import annotations

from typing import Any, Mapping

SCHEMA_FAMILY = "forward_market_observability_v1"
RAW_ENVELOPE_SCHEMA = "forward_market_observability_v1_raw_envelope/1.0.0"
CHUNK_SCHEMA = "forward_market_observability_v1_chunk/1.0.0"
MANIFEST_SCHEMA = "forward_market_observability_v1_manifest/1.0.0"
SESSION_SCHEMA = "forward_market_observability_v1_session/1.0.0"
PARSED_DERIVATIVE_SCHEMA = "forward_market_observability_v1_parsed_derivative/1.0.0"
EVENT_SCHEMA = "forward_market_observability_v1_event/1.0.0"
CONFIG_SCHEMA = "forward_market_observability_v1_config/1.0.0"
HEALTH_SCHEMA = "forward_market_observability_v1_health/1.0.0"

LEGAL_AVAILABLE_AT_RULE = "local_received_at_utc"
LEGAL_AVAILABLE_AT_IS_NOT = "exchange_event_time"

SOURCE_TYPE_LIVE = "LIVE"
SOURCE_TYPE_BACKFILL = "BACKFILL"

CHUNK_STATUS_COMPLETE = "COMPLETE"
CHUNK_STATUS_INCOMPLETE = "INCOMPLETE"
CHUNK_STATUS_QUARANTINED = "QUARANTINED"

EVENT_CLOCK_ANOMALY = "CLOCK_ANOMALY"
EVENT_DISCONNECT = "DISCONNECT"
EVENT_RECONNECT = "RECONNECT"
EVENT_GAP = "GAP"
EVENT_PARSE_ERROR = "PARSE_ERROR"
EVENT_SESSION_START = "SESSION_START"
EVENT_SESSION_STOP = "SESSION_STOP"

FORBIDDEN_SCIENTIFIC_FIELDS = frozenset(
    {
        "future_return",
        "future_mae",
        "mae",
        "drawdown",
        "prediction",
        "predictive_score",
        "beta",
        "classification",
        "correlation_with_future_price",
        "future_adverse_excursion",
        "market_06",
        "m04_fwd",
        "threshold_selected_from_data",
    }
)

RAW_ENVELOPE_REQUIRED_FIELDS = (
    "schema_version",
    "session_id",
    "source_id",
    "instrument",
    "local_received_at_utc",
    "local_received_monotonic_ns",
    "legal_available_at",
    "raw_payload_length",
    "raw_payload_sha256",
    "raw_payload",
    "transport",
)


class CollectorSchemaError(ValueError):
    """Collector record violates the frozen acquisition schema."""


def assert_no_scientific_fields(payload: Mapping[str, Any], *, where: str) -> None:
    """Fail closed if a collector record carries scientific-outcome fields."""
    keys = set(payload.keys())
    overlap = keys & FORBIDDEN_SCIENTIFIC_FIELDS
    if overlap:
        raise CollectorSchemaError(
            f"SCIENTIFIC_FIELD_FORBIDDEN:{where}:{sorted(overlap)}"
        )
    for value in payload.values():
        if isinstance(value, dict):
            assert_no_scientific_fields(value, where=where)
