"""Outcome-blind event windows. Does not read a late label or a trade."""

from __future__ import annotations

import datetime as dt

from scripts.research.level_cross_venue_reaction_discovery_v1.cohort import assemble
from scripts.research.level_cross_venue_reaction_discovery_v1.series import load_reaction_series
from scripts.research.level_touch_degradation_v1.data import load_discovery_bars

from . import constants as K


def month_of(ms: int) -> str:
    stamp = dt.datetime.fromtimestamp(int(ms) / 1000.0, tz=dt.timezone.utc)
    return f"{stamp.year:04d}-{stamp.month:02d}"


def months_covering(start_ms: int, end_ms: int) -> list[str]:
    """Months overlapped by [start_ms, end_ms)."""
    if end_ms <= start_ms:
        return []
    months = []
    cursor = month_of(start_ms)
    last = month_of(end_ms - 1)
    year, month = int(cursor[:4]), int(cursor[5:])
    while True:
        name = f"{year:04d}-{month:02d}"
        months.append(name)
        if name == last:
            break
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)
    return months


def event_window(row: dict, population: str) -> dict:
    t_ms = int(row["open_ms"])
    pre = t_ms - K.PRE60_MS
    d_ms = t_ms + K.REACTION_MS
    if pre < dt.datetime(2020, 3, 1, tzinfo=dt.timezone.utc).timestamp() * 1000:
        raise RuntimeError("pre-touch hour reaches before the March 2020 lookback")
    if d_ms > K.EVENT_END_MS:
        raise RuntimeError("reaction window reaches 2025")
    return {
        "key": f"{population}:{row['episode_id']}",
        "episode_id": row["episode_id"],
        "population": population,
        "pre_ms": pre,
        "t_ms": t_ms,
        "d_ms": d_ms,
        "touch_end_ms": t_ms + K.BAR_MS,
        "zone_low": float(row["zone_low"]),
        "zone_high": float(row["zone_high"]),
    }


def required_months(events: list[dict]) -> list[str]:
    found = set()
    for ev in events:
        for month in months_covering(ev["pre_ms"], ev["d_ms"]):
            found.add(month)
    return sorted(found)


def build_windows() -> list[dict]:
    bars = load_discovery_bars()
    venues = load_reaction_series()
    built = assemble(bars, venues)
    events = [event_window(row, "real") for row in built["real_rows"]]
    for pair in built["pairs"]:
        events.append(event_window(pair["pseudo"], "pseudo"))
    return events
