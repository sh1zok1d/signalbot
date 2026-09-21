"""Operational health metrics. Not scientific outcomes."""

from __future__ import annotations

ALLOWED_OPERATIONAL_METRICS = (
    "message_count",
    "bytes_received",
    "messages_per_sec",
    "reconnect_count",
    "parse_error_count",
    "checksum_failures",
    "invalid_observation_count",
    "clock_anomalies",
    "coverage_gaps",
    "last_receipt_age",
    "chunk_count",
)
