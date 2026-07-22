"""Stage 2.1 Data Quality & Gap Detection: pure, deterministic live-health
snapshot computation (Data Quality Contract Revision 0.2.5,
docs/STAGE2_SPEC.md §13). No DB, network, or clock — contract/computation only."""
from .gaps import compute_gap_summary
from .health import compute_data_health_snapshot, derive_data_health_status
from .models import (
    CONTINUOUS_METRICS, DataHealthSnapshot, DataQualityError, DataQualityObservation,
    DataQualityRequest, DataQualityThresholds, EVENT_DRIVEN_METRICS, GapSummary,
    HEALTH_STATUSES, LIVE_EXPECTED_INTERVAL_S, VALID_BACKFILL_STATUSES,
    VALID_COVERAGE_TYPES, VALID_METRICS, VALID_RAW_SOURCES,
)

__all__ = [
    "compute_data_health_snapshot", "compute_gap_summary", "derive_data_health_status",
    "DataQualityError", "DataQualityObservation", "DataQualityThresholds",
    "DataQualityRequest", "DataHealthSnapshot", "GapSummary",
    "VALID_METRICS", "CONTINUOUS_METRICS", "EVENT_DRIVEN_METRICS",
    "LIVE_EXPECTED_INTERVAL_S", "VALID_COVERAGE_TYPES", "VALID_BACKFILL_STATUSES",
    "VALID_RAW_SOURCES", "HEALTH_STATUSES",
]
