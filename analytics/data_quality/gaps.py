"""
Stage 2.1 interval-based gap detection — a pure, microsecond-exact helper
(Data Quality Contract Revision 0.2.5, docs/STAGE2_SPEC.md §13.8).

`compute_gap_summary(timestamps, expected_interval_s, gap_tolerance_factor)`
returns a `GapSummary` over the interior observation-to-observation deltas of a
continuous metric. No DB, no clock, no float-boundary rounding of the gap
decision: the strict comparison is done in exact integer microseconds against a
`Decimal` threshold, and `largest_gap_s` is a ceil over integer microseconds.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Iterable

from .models import DataQualityError, GapSummary

_US_PER_SECOND = 1_000_000


def _delta_us(later: datetime, earlier: datetime) -> int:
    """Exact whole-microsecond delta as an int (never a float epoch)."""
    d = later - earlier
    return d.days * 86_400 * _US_PER_SECOND + d.seconds * _US_PER_SECOND + d.microseconds


def _ceil_seconds(delta_us: int) -> int:
    """ceil(delta_us / 1_000_000) using integer arithmetic only (§13.8)."""
    return (delta_us + _US_PER_SECOND - 1) // _US_PER_SECOND


def compute_gap_summary(
    timestamps: Iterable[datetime],
    expected_interval_s: int,
    gap_tolerance_factor: float,
) -> GapSummary:
    """Detect interior gaps among continuous-metric timestamps.

    A gap exists for a consecutive pair only when
    ``exact_delta_seconds > expected_interval_s * gap_tolerance_factor``
    (strict). Timestamps are sorted and de-duplicated first; edges are never
    treated as gaps; fewer than two distinct timestamps => no gaps.
    """
    if not isinstance(expected_interval_s, int) or isinstance(expected_interval_s, bool) \
            or expected_interval_s <= 0:
        raise DataQualityError(
            f"expected_interval_s must be an int > 0 for gap detection, "
            f"got {expected_interval_s!r}")
    if not isinstance(gap_tolerance_factor, (int, float)) or isinstance(gap_tolerance_factor, bool) \
            or not float(gap_tolerance_factor) > 1:
        raise DataQualityError(
            f"gap_tolerance_factor must be a real number > 1, got {gap_tolerance_factor!r}")

    unique: list[datetime] = []
    seen = set()
    for ts in timestamps:
        if not isinstance(ts, datetime):
            raise DataQualityError(
                f"gap timestamps must be datetimes, got {type(ts).__name__}")
        if ts.tzinfo is None or ts.utcoffset() is None:
            raise DataQualityError("gap timestamps must be timezone-aware")
        if ts.utcoffset() != timedelta(0):
            raise DataQualityError("gap timestamps must be UTC (offset 0)")
        if ts not in seen:
            seen.add(ts)
            unique.append(ts)
    unique.sort()

    if len(unique) < 2:
        return GapSummary(gap_count=0, largest_gap_s=None)

    # Exact threshold in microseconds; Decimal(str(factor)) is exact per the
    # frozen contract, so the strict '>' never suffers binary-float wobble.
    threshold_us = (Decimal(expected_interval_s)
                    * Decimal(str(gap_tolerance_factor))
                    * Decimal(_US_PER_SECOND))

    gap_count = 0
    largest_gap_us = 0
    for prev, cur in zip(unique, unique[1:]):
        delta_us = _delta_us(cur, prev)
        if Decimal(delta_us) > threshold_us:
            gap_count += 1
            if delta_us > largest_gap_us:
                largest_gap_us = delta_us

    largest_gap_s = _ceil_seconds(largest_gap_us) if gap_count else None
    return GapSummary(gap_count=gap_count, largest_gap_s=largest_gap_s)
