"""Stage 2.1 Percentile Engine: pure, deterministic percentile-snapshot
computation (Percentile Contract Revision 0.2.4, docs/STAGE2_SPEC.md §12).
No DB, network, or clock — contract/computation only."""
from .compute import compute_percentile_snapshot
from .models import (
    CONFIDENCE_TIERS, CONSENSUS_SCOPE_METRICS, ConfidenceTierThresholds,
    EXCHANGE_SCOPE_METRICS, METRICS_BY_SCOPE, PercentileError, PercentileRequest,
    PercentileSample, PercentileSnapshot, VALID_SCOPES, VALID_WINDOWS,
    WINDOW_TIMEDELTAS,
)

__all__ = [
    "compute_percentile_snapshot",
    "ConfidenceTierThresholds", "PercentileError", "PercentileRequest",
    "PercentileSample", "PercentileSnapshot",
    "VALID_SCOPES", "VALID_WINDOWS", "WINDOW_TIMEDELTAS", "CONFIDENCE_TIERS",
    "EXCHANGE_SCOPE_METRICS", "CONSENSUS_SCOPE_METRICS", "METRICS_BY_SCOPE",
]
