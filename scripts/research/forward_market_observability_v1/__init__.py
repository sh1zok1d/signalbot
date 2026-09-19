"""FORWARD_MARKET_OBSERVABILITY_V1 — acquisition infrastructure.

Not a scientific experiment. Not MARKET-06. Not M04-FWD.
Does not compute future return, MAE, beta, prediction, or classification.
"""

from __future__ import annotations

from scripts.research.forward_market_observability_v1.schemas import (
    CHUNK_SCHEMA,
    FORBIDDEN_SCIENTIFIC_FIELDS,
    LEGAL_AVAILABLE_AT_RULE,
    MANIFEST_SCHEMA,
    RAW_ENVELOPE_SCHEMA,
    SCHEMA_FAMILY,
)

__all__ = [
    "CHUNK_SCHEMA",
    "FORBIDDEN_SCIENTIFIC_FIELDS",
    "LEGAL_AVAILABLE_AT_RULE",
    "MANIFEST_SCHEMA",
    "RAW_ENVELOPE_SCHEMA",
    "SCHEMA_FAMILY",
]
