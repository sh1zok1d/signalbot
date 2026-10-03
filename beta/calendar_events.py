"""Scheduled events and how big such days and hours were (PRODUCT_DECISION_V2 §2.3).

`config/beta_calendar.yaml` holds scheduled US releases (CPI, FOMC; more kinds can be added by
hand) and two recurring schedules: Deribit BTC options expiry (every Friday 08:00 UTC; the last
Friday of a month is the monthly expiry, of March / June / September / December the quarterly
one) and Binance funding settlements.

`event_size_stats` measures, on history, the range of the event hour and of the event's UTC day
against the same clock hour / days without that event (median of the previous 20 eligible
days). A ratio, its N and its spread; nothing about direction.
"""
from __future__ import annotations

import calendar as _cal
import math
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional, Sequence

import numpy as np
import yaml

from .hist_series import BAR_MS, BARS_PER_DAY, Bars

CALENDAR_PATH = Path(__file__).resolve().parent.parent / "config" / "beta_calendar.yaml"
EVENT_STATS_VERSION = "BETA_EVENT_STATS_V1"
DAY_MS = 86_400_000
HOUR_MS = 3_600_000
REFERENCE_DAYS = 20
STAT_KINDS = ("CPI", "FOMC", "EXPIRY_MONTHLY", "EXPIRY_QUARTERLY")
PUSH_KINDS = ("CPI", "FOMC")


def _parse_utc(s: str) -> datetime:
    dt = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise ValueError(f"calendar time without zone: {s!r}")
    return dt.astimezone(timezone.utc)


@lru_cache(maxsize=4)
def _load(path: str, mtime: float) -> dict:
    with open(path, encoding="utf-8") as fh:
        raw = yaml.safe_load(fh) or {}
    events = []
    for e in raw.get("events") or ():
        at = _parse_utc(e["at_utc"])
        events.append({"kind": str(e["kind"]).upper(), "at": at, "source": e.get("source"),
                       "title": e.get("title")})
    events.sort(key=lambda e: (e["at"], e["kind"]))
    return {"version": raw.get("version"), "recurring": raw.get("recurring") or {}, "events": events}


def load_calendar(path: Optional[Path] = None) -> dict:
    p = Path(path or CALENDAR_PATH)
    return _load(str(p), p.stat().st_mtime)


def event_times_ms(cal: Mapping[str, Any], kinds: Iterable[str] = ("CPI", "FOMC")) -> dict:
    out: dict = {k: [] for k in kinds}
    for e in cal["events"]:
        if e["kind"] in out:
            out[e["kind"]].append(int(e["at"].timestamp() * 1000))
    return {k: sorted(v) for k, v in out.items()}


def _last_friday(year: int, month: int) -> int:
    last = _cal.monthrange(year, month)[1]
    d = datetime(year, month, last)
    return last - (d.weekday() - 4) % 7


def expiries(start: datetime, end: datetime, recurring: Mapping[str, Any]) -> list:
    """Options expiries in [start, end): weekly, monthly or quarterly."""
    spec = recurring.get("options_expiry") or {}
    if not spec:
        return []
    wd = int(spec.get("weekday", 4))
    hh, mm = (int(x) for x in str(spec.get("time_utc", "08:00")).split(":"))
    quarters = set(spec.get("quarterly_months") or ())
    d = start.astimezone(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    out = []
    while d < end:
        if d.weekday() == wd:
            at = d.replace(hour=hh, minute=mm)
            if start <= at < end:
                monthly = d.day == _last_friday(d.year, d.month)
                kind = "EXPIRY_QUARTERLY" if monthly and d.month in quarters else \
                    "EXPIRY_MONTHLY" if monthly else "EXPIRY_WEEKLY"
                out.append({"kind": kind, "at": at, "source": "recurring"})
        d += timedelta(days=1)
    return out


def fundings(start: datetime, end: datetime, recurring: Mapping[str, Any]) -> list:
    times = recurring.get("funding_utc") or ()
    out = []
    d = start.astimezone(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    while d < end:
        for t in times:
            hh, mm = (int(x) for x in str(t).split(":"))
            at = d.replace(hour=hh, minute=mm)
            if start <= at < end:
                out.append({"kind": "FUNDING", "at": at, "source": "recurring"})
        d += timedelta(days=1)
    return out


def upcoming(cal: Mapping[str, Any], *, now: datetime, hours: float = 24.0,
             include_weekly_expiry: bool = False, include_funding: bool = False) -> list:
    end = now + timedelta(hours=hours)
    out = [e for e in cal["events"] if now <= e["at"] < end]
    for e in expiries(now, end, cal["recurring"]):
        if include_weekly_expiry or e["kind"] != "EXPIRY_WEEKLY":
            out.append(e)
    if include_funding:
        out.extend(fundings(now, end, cal["recurring"]))
    return sorted(out, key=lambda e: (e["at"], e["kind"]))


# ---- history: how big were such hours and days --------------------------------------------
def _range_pct(b: Bars, a: int, z: int) -> Optional[float]:
    if a < 0 or z > b.n or z <= a:
        return None
    seg = slice(a, z)
    if np.isfinite(b.close[seg]).mean() < 0.95:
        return None
    hi, lo = np.nanmax(b.high[seg]), np.nanmin(b.low[seg])
    o = b.open[a] if math.isfinite(b.open[a]) else np.nanmean(b.close[seg])
    return float((hi - lo) / o * 100.0)


def event_size_stats(b: Bars, cal: Mapping[str, Any], *, kinds: Sequence[str] = STAT_KINDS) -> dict:
    """Per kind: median ratio of the event hour's range and of the event day's range to the
    same clock hour / day on the previous REFERENCE_DAYS days without an event of that kind."""
    if b.n == 0:
        return {"version": EVENT_STATS_VERSION, "kinds": {}}
    start = datetime.fromtimestamp(b.t0 / 1000, tz=timezone.utc)
    end = datetime.fromtimestamp(b.end_ms / 1000, tz=timezone.utc)
    evs = [e for e in cal["events"] if start <= e["at"] < end] + expiries(start, end, cal["recurring"])
    out: dict = {"version": EVENT_STATS_VERSION, "reference_days": REFERENCE_DAYS, "kinds": {}}
    for kind in kinds:
        times = sorted(int(e["at"].timestamp() * 1000) for e in evs if e["kind"] == kind)
        if not times:
            continue
        ev_days = {t // DAY_MS for t in times}
        hour_r, day_r = [], []
        for t in times:
            i = (t - b.t0) // BAR_MS
            ev_h = _range_pct(b, int(i), int(i) + 12)
            d0 = (t // DAY_MS) * DAY_MS
            j = (d0 - b.t0) // BAR_MS
            ev_d = _range_pct(b, int(j), int(j) + BARS_PER_DAY)
            ref_h, ref_d = [], []
            k = 1
            while len(ref_h) < REFERENCE_DAYS and k < REFERENCE_DAYS * 3:
                day = t // DAY_MS - k
                k += 1
                if day in ev_days:
                    continue
                rh = _range_pct(b, int(i - (t // DAY_MS - day) * BARS_PER_DAY),
                                int(i - (t // DAY_MS - day) * BARS_PER_DAY) + 12)
                rd = _range_pct(b, int((day * DAY_MS - b.t0) // BAR_MS),
                                int((day * DAY_MS - b.t0) // BAR_MS) + BARS_PER_DAY)
                if rh is not None:
                    ref_h.append(rh)
                if rd is not None:
                    ref_d.append(rd)
            if ev_h is not None and len(ref_h) >= REFERENCE_DAYS // 2:
                hour_r.append(ev_h / float(np.median(ref_h)))
            if ev_d is not None and len(ref_d) >= REFERENCE_DAYS // 2:
                day_r.append(ev_d / float(np.median(ref_d)))
        rec: dict = {"n": len(times)}
        for name, arr in (("hour", hour_r), ("day", day_r)):
            if len(arr) >= 8:
                a = np.asarray(arr)
                rec[name] = {"n": int(a.size), "median_ratio": float(np.median(a)),
                             "q25": float(np.quantile(a, 0.25)), "q75": float(np.quantile(a, 0.75)),
                             "share_above_1": float(np.mean(a > 1.0))}
        out["kinds"][kind] = rec
    return out
