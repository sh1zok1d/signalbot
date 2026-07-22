"""
Immutable input/output models for the Stage 2.1 Data Quality & Gap Detection
core (Data Quality Contract Revision 0.2.5, docs/STAGE2_SPEC.md §13).

Pure data only — no DB, no network, no clock. Nested structures are deeply
frozen (tuples + frozen dataclasses). `DataHealthSnapshot`'s field set mirrors
the `data_health_snapshots` columns in storage/stage2_schema.sql EXCEPT
`computed_at` (DB default / writer). No invented columns, no `source_mode`, no
`status`, no `raw_source` in the output.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from types import MappingProxyType
from typing import Mapping, Optional, Sequence

# ---- frozen contract constants (§13.3 / §13.5 / §13.10 / §13.13) -----------
# Exactly five health metrics (§13.3). `mark_price` is out of Stage 2 Data
# Quality scope and is rejected.
VALID_METRICS: tuple[str, ...] = (
    "ohlcv", "taker_flow", "open_interest", "funding", "liquidations",
)
# Only `liquidations` is event-driven; the rest are continuous (§13.3/§13.6).
EVENT_DRIVEN_METRICS: frozenset = frozenset({"liquidations"})
CONTINUOUS_METRICS: frozenset = frozenset(VALID_METRICS) - EVENT_DRIVEN_METRICS

# Frozen LIVE expected-interval mapping (§13.3). `None` == liquidations (NULL).
LIVE_EXPECTED_INTERVAL_S: Mapping[str, Optional[int]] = MappingProxyType({
    "ohlcv": 60,
    "taker_flow": 60,
    "open_interest": 15,
    "funding": 15,
    "liquidations": None,
})

# Live-feed quality allow-list (§13.3 capability input).
VALID_COVERAGE_TYPES: tuple[str, ...] = ("full", "snapshot", "aggregated", "unavailable")

# Normalized backfill run states (§13.10). Supplied + echoed, never inferred.
VALID_BACKFILL_STATUSES: tuple[str, ...] = (
    "not_applicable", "not_started", "in_progress", "complete", "partial", "failed",
)

# Observation provenance (§13.4). Only `live` is accepted by the live-health core.
VALID_RAW_SOURCES: tuple[str, ...] = ("live", "backfill")

# Ordered derived report labels (§13.5). Never persisted as a column.
HEALTH_STATUSES: tuple[str, ...] = (
    "not_available", "disconnected", "connection_unknown", "no_data",
    "stale", "gap_exceeded", "ok",
)


class DataQualityError(ValueError):
    """Invalid Data Quality request / input that must fail loudly — never
    silently coerced, dropped, filtered, or defaulted (§13.14)."""


# ---- config value object (§13.13 / §13.6 threshold rules) ------------------
@dataclass(frozen=True)
class DataQualityThresholds:
    """The four resolved `defaults.data_quality` thresholds (§13.13), validated
    at construction with the SAME rules as common/stage2_config.py:
    `cadence_s`/`coverage_window_s`/`max_usable_gap_s` are ints > 0 (bool
    rejected); `gap_tolerance_factor` is a finite real > 1 (bool/NaN/±Inf
    rejected)."""
    cadence_s: int
    coverage_window_s: int
    gap_tolerance_factor: float
    max_usable_gap_s: int

    def __post_init__(self):
        for name in ("cadence_s", "coverage_window_s", "max_usable_gap_s"):
            v = getattr(self, name)
            if not isinstance(v, int) or isinstance(v, bool) or v <= 0:
                raise DataQualityError(f"{name} must be an int > 0, got {v!r}")
        f = self.gap_tolerance_factor
        if not isinstance(f, (int, float)) or isinstance(f, bool):
            raise DataQualityError(
                f"gap_tolerance_factor must be a real number, got {f!r}")
        if not math.isfinite(float(f)):
            raise DataQualityError(f"gap_tolerance_factor must be finite, got {f!r}")
        if not float(f) > 1:
            raise DataQualityError(f"gap_tolerance_factor must be > 1, got {f!r}")


# ---- inputs ----------------------------------------------------------------
@dataclass(frozen=True)
class DataQualityObservation:
    """One accepted raw live row's identity + timestamp + provenance (§13.4).
    No metric payload is required by this core: the caller only constructs an
    observation from a row whose metric payload is complete. Carries NO
    `source_mode` and NO `calculation_version`."""
    exchange: str
    symbol: str
    market_type: str
    metric: str
    ts: datetime
    raw_source: str


@dataclass(frozen=True)
class GapSummary:
    """Result of interval-based gap detection over continuous timestamps
    (§13.8). `largest_gap_s` is None when no oversized interior gap exists."""
    gap_count: int
    largest_gap_s: Optional[int]


@dataclass(frozen=True)
class DataQualityRequest:
    """A fully caller-supplied live-health request (§13.0). Everything needed to
    classify one `(identity, snapshot_ts, calculation_version)` live-health row
    is present; the core reads no external state."""
    # identity
    symbol: str
    exchange: str
    market_type: str
    metric: str
    snapshot_ts: datetime
    observations: Sequence[DataQualityObservation]

    # capability + connection + backfill facts (supplied, never inferred)
    live_supported: bool
    historical_supported: bool
    coverage_type: str
    expected_freshness_s: Optional[int]
    expected_interval_s: Optional[int]
    connection_up: Optional[bool]
    backfill_status: str

    # resolved config thresholds
    thresholds: DataQualityThresholds

    # provenance / version
    config_hash: str
    config_version: str
    code_version: str
    feature_schema_version: int
    calculation_version: str

    def __post_init__(self):
        # Freeze the observation sequence so the request is fully immutable and
        # the caller's list can never be mutated through us. Order-independent.
        object.__setattr__(self, "observations", tuple(self.observations))


# ---- output ----------------------------------------------------------------
@dataclass(frozen=True)
class DataHealthSnapshot:
    """Exactly the `data_health_snapshots` columns (storage/stage2_schema.sql)
    EXCEPT `computed_at`. No `status`, no `source_mode`, no `raw_source`."""
    # identity
    symbol: str
    exchange: str
    market_type: str
    metric: str
    snapshot_ts: datetime

    # computed live-health result
    last_event_at: Optional[datetime]
    expected_interval_s: Optional[int]
    lateness_ms: Optional[int]
    gap_count: int
    largest_gap_s: Optional[int]
    backfill_status: str
    coverage_window_start: datetime
    coverage_window_end: datetime
    is_stale: bool
    is_usable: bool

    # provenance / version (computed_at intentionally omitted — DB default)
    config_hash: str
    config_version: str
    code_version: str
    feature_schema_version: int
    calculation_version: str
