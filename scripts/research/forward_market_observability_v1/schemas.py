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

# Response validity (frozen contract): a REST observation counts as valid
# only with an expected successful HTTP status AND a schema-valid native
# payload. An HTTP error body (451, 500, ...) is retained as operational
# transport evidence but is NEVER a valid market observation.
REST_SUCCESS_HTTP_STATUS = 200

# Native fields every source's payload must carry, non-null, to count as a
# valid observation. Keyed by source_id so config/source-set changes are
# visible instead of silently accepted.
SOURCE_REQUIRED_NATIVE_FIELDS: dict[str, tuple[str, ...]] = {
    "BINANCE_UM_BTCUSDT_MARK_PRICE_WS": (
        "mark_price",
        "funding_rate",
        "next_funding_time",
    ),
    "BINANCE_UM_BTCUSDT_PREMIUM_INDEX_REST": (
        "mark_price",
        "index_price",
    ),
    "BINANCE_UM_BTCUSDT_OPEN_INTEREST_REST": (
        "open_interest",
    ),
}


class CollectorSchemaError(ValueError):
    """Collector record violates the frozen acquisition schema."""


def classify_source_observation_validity(
    source_id: str,
    *,
    transport: Mapping[str, Any],
    native: Mapping[str, Any] | None,
    parse_error: str | None,
) -> bool:
    """True only for a genuine, schema-valid native market observation.

    REST: requires the expected successful HTTP status AND every required
    native field present and non-null. An HTTP 4xx/5xx body -- including
    451 restricted-location and 500 -- is never valid, regardless of
    whether its bytes happen to parse as JSON.

    WebSocket: requires a schema-valid native payload (no HTTP status to
    check); a connection notice or malformed frame is never valid.
    """
    if parse_error is not None or native is None:
        return False
    if source_id not in SOURCE_REQUIRED_NATIVE_FIELDS:
        # An unrecognized/unfrozen source can never be validated as ready.
        return False
    transport_kind = transport.get("transport")
    if transport_kind == "rest":
        status = transport.get("http_status")
        if status != REST_SUCCESS_HTTP_STATUS:
            return False
    elif transport_kind == "websocket":
        pass
    else:
        return False
    required = SOURCE_REQUIRED_NATIVE_FIELDS[source_id]
    return all(native.get(field) not in (None, "") for field in required)


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
