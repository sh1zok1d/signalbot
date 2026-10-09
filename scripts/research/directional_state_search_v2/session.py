"""NYSE session clocks on the 5m grid (America/New_York, DST-aware; NYSE_HOLIDAY_CALENDAR_ARCHIVE_V0 full closures)."""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np

from . import constants as K

ROOT = Path(__file__).resolve().parents[3]
NYSE_EVENTS = ROOT / "docs/research_data/NYSE_HOLIDAY_CALENDAR_ARCHIVE_V0/EVENTS.json"
NY = ZoneInfo("America/New_York")


NYSE_EVENTS_SHA256 = "69ee28a5192e4eb69e538e72f49164af820b2eeb841f380f24e337b2acef0be2"


def nyse_closures() -> set[str]:
    import hashlib
    if hashlib.sha256(NYSE_EVENTS.read_bytes()).hexdigest() != NYSE_EVENTS_SHA256:
        raise SystemExit("NYSE_CALENDAR_DRIFT")
    events = json.loads(NYSE_EVENTS.read_text())
    return {e["OBSERVED_OR_CLOSURE_DATE"] for e in events if e["EVENT_TYPE"] == "FULL_DAY_CLOSURE"}


def trading_days() -> list[dt.date]:
    closed = nyse_closures()
    d, end = dt.date(2020, 1, 1), dt.date(2024, 12, 31)
    out = []
    while d <= end:
        if d.weekday() < 5 and d.isoformat() not in closed:
            out.append(d)
        d += dt.timedelta(days=1)
    return out


def ny_ms(day: dt.date, hh: int, mm: int) -> int:
    return int(dt.datetime(day.year, day.month, day.day, hh, mm, tzinfo=NY).timestamp() * 1000)


def bar_closing_at(open_ms: np.ndarray, t_ms: int) -> int:
    """Index of the 5m bar whose close is exactly t_ms."""
    i = (t_ms - K.BAR_MS - int(open_ms[0])) // K.BAR_MS
    if i < 0 or i >= open_ms.size or int(open_ms[i]) != t_ms - K.BAR_MS:
        raise SystemExit("SESSION_CLOCK_OFF_GRID")
    return int(i)


def _rv_ending(close: np.ndarray, i: int, w: int = K.LOOKBACK_24H) -> float:
    r = np.diff(np.log(close[i - w:i + 1]))
    return float(np.sqrt(np.sum(r * r)))


def session_rows(bars: dict) -> dict:
    """One row per NYSE trading day 2020-01-02 .. 2024-12-31 for each session object.

    US_OPEN_DRIVE: T = 10:00 ET. DRIVE_30M_Z = log(P[10:00]/P[09:30]) / RV_24H ending at 09:30 ET.
    SESSION_HANDOFF: T = 09:30 ET. EU_DRIFT_Z = log(P[09:30]/P[03:00]) / RV_24H ending at 03:00 ET.
    P[t] = close of the 5m bar whose close is t. Returns anchor indices (bar closing at T) and states."""
    o, c = bars["open_ms"], bars["close"]
    us_i, us_s, ho_i, ho_s = [], [], [], []
    for d in trading_days():
        i930 = bar_closing_at(o, ny_ms(d, 9, 30))
        i1000 = bar_closing_at(o, ny_ms(d, 10, 0))
        i300 = bar_closing_at(o, ny_ms(d, 3, 0))
        if i300 - K.LOOKBACK_24H < 0:
            continue
        us_i.append(i1000)
        us_s.append(np.log(c[i1000] / c[i930]) / _rv_ending(c, i930))
        ho_i.append(i930)
        ho_s.append(np.log(c[i930] / c[i300]) / _rv_ending(c, i300))
    return {"US_OPEN_DRIVE": (np.array(us_i), np.array(us_s)), "SESSION_HANDOFF": (np.array(ho_i), np.array(ho_s))}


def placebo_states(close: np.ndarray, idx: np.ndarray) -> dict:
    """The same statistics at every anchor i of the main grid (placebo clocks):
    DRIVE_30M_Z(i) = log(c_i / c_{i-6}) / RV_24H ending at i-6;  EU_DRIFT_Z(i) = log(c_i / c_{i-78}) / RV_24H ending at i-78."""
    lc = np.log(close)
    r = np.zeros(close.size)
    r[1:] = np.diff(lc)
    cs = np.zeros(close.size + 1)
    np.cumsum(r * r, out=cs[1:])
    def rv_end(j):
        return np.sqrt(cs[j + 1] - cs[j + 1 - K.LOOKBACK_24H])
    out = {}
    for name, lag in (("US_OPEN_DRIVE", 6), ("SESSION_HANDOFF", 78)):
        ok = idx - lag - K.LOOKBACK_24H >= 0
        j = np.where(ok, idx - lag, K.LOOKBACK_24H)
        v = (lc[idx] - lc[j]) / rv_end(j)
        out[name] = np.where(ok, v, np.nan)
    return out
