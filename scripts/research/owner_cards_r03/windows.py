"""Calendar and window geometry. Outcome-blind: nothing here reads a price.

A window is (t0_ms, length_minutes). Local-clock windows are resolved with the
IANA tz database (America/New_York, Europe/London), so DST is exact.
"""

from __future__ import annotations

import datetime as dt
from zoneinfo import ZoneInfo

from . import constants as K

UTC = dt.timezone.utc
ZONES = {"UTC": UTC, "America/New_York": ZoneInfo("America/New_York"), "Europe/London": ZoneInfo("Europe/London")}


def utc_date(ms: int) -> dt.date:
    return dt.datetime.fromtimestamp(ms / 1000, tz=UTC).date()


def date_ms(d: dt.date) -> int:
    return int(dt.datetime(d.year, d.month, d.day, tzinfo=UTC).timestamp() * 1000)


def local_window_start_ms(d: dt.date, zone: str, hhmm: str) -> int:
    """UTC ms of the instant `hhmm` local time on local date d."""
    hh, mm = (int(x) for x in hhmm.split(":"))
    local = dt.datetime(d.year, d.month, d.day, hh, mm, tzinfo=ZONES[zone])
    return int(local.astimezone(UTC).timestamp() * 1000)


def window_for(window_id: str, d: dt.date, hour: int | None = None) -> tuple[int, int]:
    zone, start, length = K.WINDOW_DEFS[window_id]
    if start == "HOURLY":
        if hour is None:
            raise ValueError("hourly window needs an hour")
        return date_ms(d) + hour * K.HOUR_MS, length
    return local_window_start_ms(d, zone, start), length


def iso_week_key(d: dt.date) -> str:
    y, w, _ = d.isocalendar()
    return f"{y}-W{w:02d}"


def days_in_range(start_ms: int, end_ms: int):
    d = utc_date(start_ms)
    end = utc_date(end_ms - 1)
    while d <= end:
        yield d
        d += dt.timedelta(days=1)


def last_friday_of_month(year: int, month: int) -> dt.date:
    nxt = dt.date(year + (month == 12), (month % 12) + 1, 1)
    d = nxt - dt.timedelta(days=1)
    while d.weekday() != 4:
        d -= dt.timedelta(days=1)
    return d


def window_definition_key(window_id: str, hour: int | None) -> str:
    return window_id if hour is None else f"{window_id}:{hour:02d}"
