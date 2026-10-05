"""UTC day type of a rolling window (C1 same-day-type reference, docs/BETA_C1_DAY_TYPE_BASELINE_V1.md).

Exactly the definition evaluated in WEEKDAY_WEEKEND_BASELINE_UNIT_V2: a window is WEEKEND when the
UTC calendar date of its START is a Saturday or Sunday. No local time zone, no DST.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from .state_tape import BUCKET

WEEKEND = "WEEKEND"
WEEKDAY = "WEEKDAY"
MIN_SAME_TYPE_DATES = 8


def utc_date(ts: datetime) -> date:
    if ts.tzinfo is None:
        raise ValueError("day type needs an aware UTC timestamp")
    return ts.astimezone(timezone.utc).date()


def date_type(d: date) -> str:
    return WEEKEND if d.weekday() >= 5 else WEEKDAY


def window_start(end_bucket: datetime, n: int) -> datetime:
    """Start of the n-bucket window whose last (inclusive) bucket opens at end_bucket."""
    return end_bucket - (n - 1) * BUCKET


def window_start_date(end_bucket: datetime, n: int) -> date:
    return utc_date(window_start(end_bucket, n))


def window_day_type(end_bucket: datetime, n: int) -> str:
    return date_type(window_start_date(end_bucket, n))


def tod_day_type(window_end: datetime, prior_days: int) -> str:
    """Type of TOD prior day d: the date of the central sample's window start, W - d days - 1h."""
    return date_type(utc_date(window_end - timedelta(days=prior_days) - timedelta(hours=1)))
