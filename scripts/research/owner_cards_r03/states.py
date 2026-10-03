"""Outcome-blind unit construction for the twelve R03 hypotheses.

A unit is {UNIT_ID, YEAR, STATE: [(t0_ms, minutes, defkey)], COMPARATOR: [...]}.
Calendar hypotheses (cards A and C) read no market value at all. Panel
hypotheses (card B) read the spot panel's own closes and quote volumes up to
the decision boundary T, never the BTC target.
"""

from __future__ import annotations

import datetime as dt

import numpy as np

from . import constants as K
from . import windows as W


def _unit(unit_id: str, year: int, state: list, comparator: list) -> dict:
    return {"UNIT_ID": unit_id, "YEAR": year, "STATE": state, "COMPARATOR": comparator}


def _w(window_id: str, d: dt.date, hour: int | None = None) -> tuple[int, int, str]:
    t0, length = W.window_for(window_id, d, hour)
    return (t0, length, W.window_definition_key(window_id, hour))


def _weeks(start_ms: int, end_ms: int) -> dict[str, list[dt.date]]:
    weeks: dict[str, list[dt.date]] = {}
    for d in W.days_in_range(start_ms, end_ms):
        weeks.setdefault(W.iso_week_key(d), []).append(d)
    return {k: v for k, v in weeks.items() if len(v) == 7}


def _months(start_ms: int, end_ms: int) -> dict[str, list[dt.date]]:
    months: dict[str, list[dt.date]] = {}
    for d in W.days_in_range(start_ms, end_ms):
        months.setdefault(f"{d.year}-{d.month:02d}", []).append(d)
    return months


def _closure_dates(nyse: list[dict] | None) -> tuple[set, set]:
    full, early = set(), set()
    for e in nyse or []:
        d = dt.date.fromisoformat(e["EVENT_DATE"])
        (full if e["EVENT_TYPE"] == "FULL_DAY_CLOSURE" else early).add(d)
    return full, early


def units_weekly(window_id: str, state_weekday: int, comp_weekdays: tuple[int, ...],
                 start_ms: int, end_ms: int, *, exclude_state: set | None = None) -> list[dict]:
    out = []
    for key, days in sorted(_weeks(start_ms, end_ms).items()):
        state = [d for d in days if d.weekday() == state_weekday and d not in (exclude_state or set())]
        comp = [d for d in days if d.weekday() in comp_weekdays]
        if not state or not comp:
            continue
        out.append(_unit(key, state[0].year, [_w(window_id, d) for d in state], [_w(window_id, d) for d in comp]))
    return out


def units_monthly_last_friday(window_id: str, start_ms: int, end_ms: int) -> list[dict]:
    out = []
    for key, days in sorted(_months(start_ms, end_ms).items()):
        y, m = (int(x) for x in key.split("-"))
        last = W.last_friday_of_month(y, m)
        if last not in days:
            continue
        others = [d for d in days if d.weekday() == 4 and d != last]
        if not others:
            continue
        out.append(_unit(key, y, [_w(window_id, last)], [_w(window_id, d) for d in others]))
    return out


def units_weekend_hours(start_ms: int, end_ms: int) -> list[dict]:
    out = []
    for key, days in sorted(_weeks(start_ms, end_ms).items()):
        state = [_w("UTC_HOUR_60", d, h) for d in days if d.weekday() >= 5 for h in range(24)]
        comp = [_w("UTC_HOUR_60", d, h) for d in days if d.weekday() in (1, 2, 3) for h in range(24)]
        out.append(_unit(key, days[0].year, state, comp))
    return out


def units_closure_days(window_id: str, start_ms: int, end_ms: int, nyse: list[dict]) -> list[dict]:
    full, _ = _closure_dates(nyse)
    weeks = _weeks(start_ms, end_ms)
    out = []
    for d in sorted(full):
        key = W.iso_week_key(d)
        if d.weekday() >= 5 or key not in weeks:
            continue
        comp = [x for x in weeks[key] if x.weekday() < 5 and x not in full]
        if not comp:
            continue
        out.append(_unit(d.isoformat(), d.year, [_w(window_id, d)], [_w(window_id, x) for x in comp]))
    return out


# ---------------------------------------------------------------- panel states
def panel_day_metrics(panel: dict[str, dict], excluded: dict[str, str], start_ms: int, end_ms: int) -> dict:
    """Per UTC day d (bars closed at T = d+1 00:00): dispersion, breadth, shock fraction, BTC share.

    Universe at d: not excluded, at least 30 prior days present, in the top 100 by the
    median quote volume over the 30 days before d. BTC itself is in the universe.
    """
    symbols = [s for s in sorted(panel) if s not in excluded and s.endswith("USDT")]
    days = np.arange(start_ms - K.PANEL_UNIVERSE_HISTORY_DAYS * K.DAY_MS, end_ms, K.DAY_MS)
    idx = {int(t): i for i, t in enumerate(days)}
    n_d, n_s = days.size, len(symbols)
    close = np.full((n_d, n_s), np.nan)
    quote = np.full((n_d, n_s), np.nan)
    for j, s in enumerate(symbols):
        t = panel[s]["open_ms"]
        rows = np.array([idx.get(int(x), -1) for x in t])
        ok = rows >= 0
        close[rows[ok], j] = panel[s]["close"][ok]
        quote[rows[ok], j] = panel[s]["quote"][ok]
    btc = symbols.index("BTCUSDT")
    logret = np.full_like(close, np.nan)
    logret[1:] = np.log(close[1:] / close[:-1])
    out = {"day_ms": [], "n_universe": [], "dispersion": [], "breadth": [], "shock": [], "btc_share": []}
    H = K.PANEL_UNIVERSE_HISTORY_DAYS
    for i in range(H, n_d):
        if int(days[i]) < start_ms:
            continue
        hist = quote[i - H:i]
        present = np.sum(np.isfinite(hist), axis=0) >= H
        med = np.where(present, np.nanmedian(np.where(np.isfinite(hist), hist, np.nan), axis=0), np.nan)
        today_ok = np.isfinite(logret[i]) & np.isfinite(quote[i]) & present
        order = np.argsort(-np.where(today_ok, med, -np.inf), kind="mergesort")
        universe = [j for j in order[:K.PANEL_UNIVERSE_TOP_N] if today_ok[j]]
        n = len(universe)
        if n < K.PANEL_MIN_SYMBOLS or btc not in universe:
            vals = (np.nan, np.nan, np.nan, np.nan)
        else:
            r = logret[i, universe]
            q = quote[i, universe]
            vals = (
                float(np.std(r, ddof=1)),
                float(abs(np.mean(r > 0) - 0.5)),
                float(np.mean(q >= K.VOLUME_SHOCK_MULTIPLE * med[universe])),
                float(quote[i, btc] / np.sum(q)),
            )
        out["day_ms"].append(int(days[i])); out["n_universe"].append(n)
        for k, v in zip(("dispersion", "breadth", "shock", "btc_share"), vals):
            out[k].append(v)
    return {k: np.array(v) for k, v in out.items()}


def trailing_quantile_states(values: np.ndarray, q: float, trailing: int, *, low: bool = False) -> np.ndarray:
    """state[i] = values[i] >= quantile_q(values[i-trailing:i]) (or <= for low). Past-only."""
    n = values.size
    state = np.zeros(n, dtype=bool)
    defined = np.zeros(n, dtype=bool)
    for i in range(trailing, n):
        hist = values[i - trailing:i]
        hist = hist[np.isfinite(hist)]
        if hist.size < trailing * 0.8 or not np.isfinite(values[i]):
            continue
        thr = float(np.quantile(hist, q))
        defined[i] = True
        state[i] = values[i] <= thr if low else values[i] >= thr
    return state, defined


PANEL_METRIC = {"R03-B1": ("dispersion", False), "R03-B2": ("breadth", False),
                "R03-B3": ("shock", False), "R03-B4": ("btc_share", True)}


def units_panel(hid: str, metrics: dict, start_ms: int, end_ms: int) -> tuple[list[dict], dict]:
    metric, low = PANEL_METRIC[hid]
    q = 1.0 - K.PANEL_STATE_QUANTILE if low else K.PANEL_STATE_QUANTILE
    state, defined = trailing_quantile_states(metrics[metric], q, K.PANEL_TRAILING_DAYS, low=low)
    by_month: dict[str, dict] = {}
    for i, day in enumerate(metrics["day_ms"]):
        day = int(day)
        T = day + K.DAY_MS  # decision boundary: the panel day is complete at T
        if not defined[i] or T < start_ms or T + K.DAY_MS > end_ms:
            continue
        d = W.utc_date(T)
        key = f"{d.year}-{d.month:02d}"
        win = (T, 1440, "UTC_DAY_1440")
        by_month.setdefault(key, {"S": [], "C": [], "Y": d.year})
        by_month[key]["S" if state[i] else "C"].append(win)
    units = [_unit(k, v["Y"], v["S"], v["C"]) for k, v in sorted(by_month.items()) if v["S"] and v["C"]]
    diag = {"DEFINED_DAYS": int(defined.sum()), "STATE_DAYS": int((state & defined).sum()),
            "MONTHS_WITH_BOTH": len(units)}
    return units, diag


# ---------------------------------------------------------------- dispatch
def build_units(hid: str, surface: str, *, nyse: list[dict] | None = None, metrics: dict | None = None) -> list[dict]:
    """surface: DISCOVERY (Binance 2020-2024) or REPLICATION (BitMEX 2017-2019)."""
    if surface == "DISCOVERY":
        start, end = K.DISCOVERY_START_MS, K.DISCOVERY_END_MS
    elif surface == "REPLICATION":
        start, end = K.BITMEX_START_MS, K.BITMEX_END_MS
    else:
        raise ValueError(surface)
    full, early = _closure_dates(nyse)
    if hid == "R03-A1":
        return units_weekly("UTC_0800_60", 4, (0, 1, 2, 3), start, end)
    if hid == "R03-A2":
        return units_monthly_last_friday("UTC_0800_60", start, end)
    if hid == "R03-A3":
        s = max(start, 1514764800000) if surface == "REPLICATION" else start  # CME from 2018-01 on BitMEX
        return units_monthly_last_friday("LONDON_1600_60", s, end)
    if hid == "R03-A4":
        return units_weekly("UTC_0400_240", 4, (0, 1, 2, 3), start, end)
    if hid == "R03-C1":
        return units_weekend_hours(start, end)
    if hid == "R03-C2":
        return units_weekly("NY_0930_60", 0, (1, 2, 3), start, end, exclude_state=full)
    if hid == "R03-C3":
        if surface == "REPLICATION":
            return []
        return units_closure_days("NY_0930_60", start, end, nyse or [])
    if hid == "R03-C4":
        return units_weekly("NY_1500_60", 4, (1, 2, 3), start, end, exclude_state=full | early)
    if hid.startswith("R03-B"):
        if surface == "REPLICATION":
            return []
        if metrics is None:
            raise ValueError("panel metrics required")
        return units_panel(hid, metrics, start, end)[0]
    raise KeyError(hid)


def unit_counts(units: list[dict]) -> dict:
    active = sum(len(u["STATE"]) for u in units)
    inactive = sum(len(u["COMPARATOR"]) for u in units)
    by_year: dict[str, int] = {}
    for u in units:
        by_year[str(u["YEAR"])] = by_year.get(str(u["YEAR"]), 0) + 1
    return {"UNITS": len(units), "ACTIVE_WINDOWS": active, "INACTIVE_WINDOWS": inactive, "UNITS_BY_YEAR": by_year}
