"""Calendar unit construction for AUTOGEN_G01. Outcome-blind: nothing here reads a price,
a volume or a trade count. Windows are (t0_ms, length_minutes, standardization_key).

Card A (turn of month), unit = calendar month m:
- A1/A2 state days: the last UTC day of month m-1 (unless it is that month's last Friday,
  the monthly derivatives expiry) and days 1-3 of m; comparator days: 8-21 of m.
- A3 state: 23:00-24:00 UTC on the last day of m; comparator: the same hour on days 8-21.
- Every day in the fixed holiday windows (Dec 24-Jan 2, Oct 1-7) is excluded from both roles.
- Standardization key: target window and weekday class (WD = Mon-Fri, WE = Sat-Sun).

Card B (ETF fixing window), unit = ISO week of NYSE full trading days (no full closure, no
early close, Mon-Fri). Each day carries the fixing hour 15:00-16:00 New York and the two
preceding hours; era PRE through 2024-01-07, POST from 2024-01-15, the launch week dropped.
"""

from __future__ import annotations

import datetime as dt

from scripts.research.owner_cards_r03 import windows as RW

from . import constants as K

UTC = dt.timezone.utc


def in_holiday_window(d: dt.date) -> bool:
    for (m0, d0), (m1, d1) in K.HOLIDAY_WINDOWS:
        if (m0, d0) <= (m1, d1):
            if (m0, d0) <= (d.month, d.day) <= (m1, d1):
                return True
        elif (d.month, d.day) >= (m0, d0) or (d.month, d.day) <= (m1, d1):
            return True
    return False


def wd_class(d: dt.date) -> str:
    return "WE" if d.weekday() >= 5 else "WD"


def _in_surface(d: dt.date, start_ms: int, end_ms: int) -> bool:
    t = RW.date_ms(d)
    return start_ms <= t and t + K.DAY_MS <= end_ms


def _months(start_ms: int, end_ms: int) -> list[tuple[int, int]]:
    d = RW.utc_date(start_ms)
    end = RW.utc_date(end_ms - 1)
    out = []
    y, m = d.year, d.month
    while (y, m) <= (end.year, end.month):
        out.append((y, m))
        y, m = (y + (m == 12), m % 12 + 1)
    return out


def _last_day(y: int, m: int) -> dt.date:
    return dt.date(y + (m == 12), m % 12 + 1, 1) - dt.timedelta(days=1)


def day_window(d: dt.date) -> list:
    return [RW.date_ms(d), 1440, f"UTC_DAY:{wd_class(d)}"]


def hour23_window(d: dt.date) -> list:
    return [RW.date_ms(d) + K.MONTH_END_HOUR_UTC * K.HOUR_MS, 60, f"UTC_H23:{wd_class(d)}"]


def tom_state_days(y: int, m: int, start_ms: int, end_ms: int) -> list[dt.date]:
    first = dt.date(y, m, 1)
    prev_last = first - dt.timedelta(days=1)
    days = []
    if prev_last != RW.last_friday_of_month(prev_last.year, prev_last.month):
        days.append(prev_last)
    days += [dt.date(y, m, k) for k in K.TOM_FIRST_DAYS]
    return [d for d in days if not in_holiday_window(d) and _in_surface(d, start_ms, end_ms)]


def comparator_days(y: int, m: int, start_ms: int, end_ms: int) -> list[dt.date]:
    days = [dt.date(y, m, k) for k in K.COMPARATOR_DAYS]
    return [d for d in days if not in_holiday_window(d) and _in_surface(d, start_ms, end_ms)]


def units_card_a(hid: str, start_ms: int, end_ms: int) -> list[dict]:
    units = []
    for y, m in _months(start_ms, end_ms):
        comp = comparator_days(y, m, start_ms, end_ms)
        if hid in ("G01-A1", "G01-A2"):
            state = [day_window(d) for d in tom_state_days(y, m, start_ms, end_ms)]
            comparator = [day_window(d) for d in comp]
        elif hid == "G01-A3":
            last = _last_day(y, m)
            ok = not in_holiday_window(last) and _in_surface(last, start_ms, end_ms)
            state = [hour23_window(last)] if ok else []
            comparator = [hour23_window(d) for d in comp]
        else:
            raise ValueError(hid)
        if state and comparator:
            units.append({"UNIT_ID": f"{y}-{m:02d}", "YEAR": y, "STATE": state, "COMPARATOR": comparator})
    return units


def nyse_trading_days(start_ms: int, end_ms: int, nyse: list[dict]) -> list[dt.date]:
    closed = {dt.date.fromisoformat(e["EVENT_DATE"]) for e in nyse
              if e["EVENT_TYPE"] in ("FULL_DAY_CLOSURE", "EARLY_CLOSE") and e.get("EVENT_DATE")}
    return [d for d in RW.days_in_range(start_ms, end_ms) if d.weekday() < 5 and d not in closed]


def ny_hour_window(d: dt.date, hhmm: str) -> list:
    return [RW.local_window_start_ms(d, K.NY_ZONE, hhmm), 60, "NY_13_15"]


def era_of(d: dt.date) -> str | None:
    if d <= dt.date.fromisoformat(K.PRE_LAST_DATE):
        return "PRE"
    if d >= dt.date.fromisoformat(K.POST_FIRST_DATE):
        return "POST"
    return None


def units_card_b(start_ms: int, end_ms: int, nyse: list[dict]) -> list[dict]:
    weeks: dict[str, dict] = {}
    for d in nyse_trading_days(start_ms, end_ms, nyse):
        era = era_of(d)
        if era is None:
            continue
        key = RW.iso_week_key(d)
        # year and quarter of the week's first in-surface trading day
        u = weeks.setdefault(key, {"UNIT_ID": key, "YEAR": d.year, "ERA": era,
                                   "QUARTER": (d.month - 1) // 3 + 1, "DAYS": []})
        if u["ERA"] != era:
            raise RuntimeError(f"week {key} mixes eras")
        u["DAYS"].append({"DATE": d.isoformat(), "FIX": ny_hour_window(d, K.NY_FIX_HOUR),
                          "ADJ": [ny_hour_window(d, h) for h in K.NY_ADJACENT_HOURS]})
    return [weeks[k] for k in sorted(weeks)]


def build_units(hid: str, surface: str, *, nyse: list[dict] | None = None) -> list[dict]:
    if surface == "DISCOVERY":
        start, end = K.DISCOVERY_START_MS, K.DISCOVERY_END_MS
    elif surface == "REPLICATION":
        start, end = K.BITMEX_START_MS, K.BITMEX_END_MS
    else:
        raise ValueError(surface)
    if K.HYPOTHESIS_BY_ID[hid]["CARD"] == "G01-A":
        return units_card_a(hid, start, end)
    if surface != "DISCOVERY":
        return []
    return units_card_b(start, end, nyse or [])


def unit_counts(units: list[dict]) -> dict:
    if units and "DAYS" in units[0]:
        pre = [u for u in units if u["ERA"] == "PRE"]
        post = [u for u in units if u["ERA"] == "POST"]
        return {"UNITS": len(units), "PRE_UNITS": len(pre), "POST_UNITS": len(post),
                "PRE_DAYS": sum(len(u["DAYS"]) for u in pre), "POST_DAYS": sum(len(u["DAYS"]) for u in post),
                "ACTIVE_WINDOWS": sum(len(u["DAYS"]) for u in post), "INACTIVE_WINDOWS": sum(len(u["DAYS"]) for u in pre),
                "UNITS_BY_YEAR": _by_year(units)}
    return {"UNITS": len(units),
            "ACTIVE_WINDOWS": sum(len(u["STATE"]) for u in units),
            "INACTIVE_WINDOWS": sum(len(u["COMPARATOR"]) for u in units),
            "UNITS_BY_YEAR": _by_year(units)}


def _by_year(units: list[dict]) -> dict:
    out: dict[str, int] = {}
    for u in units:
        out[str(u["YEAR"])] = out.get(str(u["YEAR"]), 0) + 1
    return dict(sorted(out.items()))
