"""Formation geometry of the anchor's completed source period.

Every value here is fixed when that period closes, which is before the level's active
period opens. The active period's bars are not read. Quote volume is the Binance quote
field. Taker-buy quote is not read.
"""

from __future__ import annotations

import math
from typing import Optional

import numpy as np

from beta import levels as LV
from beta.hist_series import Bars

from scripts.research.level_touch_degradation_v1.events import _expected_bars

from . import constants as K


def _finite_share(values: np.ndarray) -> float:
    if values.size == 0:
        return 0.0
    return float(np.isfinite(values).mean())


def period_catalog(bars: Bars) -> dict[str, list[dict]]:
    """Completed-period records, in key order, for DAY, WEEK and MONTH."""
    keys = LV.period_keys(bars)
    out: dict[str, list[dict]] = {}
    for family, name in (("DAY", "day"), ("WEEK", "week"), ("MONTH", "month")):
        rows = []
        for period in LV._period_table(bars, keys[name]):
            first, last = int(period["first"]), int(period["last"])
            sl = slice(first, last + 1)
            high = float(period["high"])
            low = float(period["low"])
            open_ = float(period["open"])
            rel = (high - low) / open_ if math.isfinite(open_) and open_ > 0 and math.isfinite(high) and math.isfinite(low) else math.nan
            quote = bars.quote[sl]
            qok = np.isfinite(quote) & (quote >= 0)
            qshare = float(qok.mean()) if quote.size else 0.0
            qsum = float(quote[qok].sum()) if np.any(qok) else math.nan
            close = bars.close[sl]
            last_close = float(close[-1]) if close.size and math.isfinite(close[-1]) else math.nan
            rows.append({
                "key": int(period["key"]),
                "first": first,
                "last": last,
                "open": open_,
                "high": high,
                "low": low,
                "range_rel": rel,
                "quote_sum": qsum,
                "quote_ok": bool(qshare >= K.MIN_PRESENT and math.isfinite(qsum) and qsum > 0),
                "close": last_close,
                "full": bool(LV._full_period(period, _expected_bars(family))),
            })
        out[family] = rows
    return out


def _priors(rows: list[dict], source_key: int, field: str, *, positive: bool) -> list[float]:
    vals = []
    for row in rows:
        if int(row["key"]) >= int(source_key) or not row["full"]:
            continue
        value = row.get(field)
        if value is None or not math.isfinite(float(value)):
            continue
        if positive and float(value) <= 0:
            continue
        if field == "quote_sum" and not row["quote_ok"]:
            continue
        vals.append(float(value))
    return vals[-K.FORMATION_BASE:]


def _log_ratio(current: float, history: list[float]) -> float:
    if len(history) < K.FORMATION_MIN or not math.isfinite(current) or current <= 0:
        return math.nan
    base = float(np.median(np.asarray(history, dtype=float)))
    if not math.isfinite(base) or base <= 0:
        return math.nan
    return math.log(current / base)


def formation_of(catalog: dict[str, list[dict]], bars: Bars, *, family: str, source_key: int,
                 side: int) -> dict:
    """Anchor formation features. Missing values are NaN. No touch bar is read."""
    empty = {
        "formation_range": math.nan,
        "formation_volume": math.nan,
        "close_off_extreme": math.nan,
        "extreme_timing": math.nan,
        "extreme_density": math.nan,
    }
    rows = catalog.get(family) or []
    source = next((row for row in rows if int(row["key"]) == int(source_key) and row["full"]), None)
    if source is None or side not in (1, -1):
        return empty
    empty["formation_range"] = _log_ratio(float(source["range_rel"]), _priors(rows, source_key, "range_rel", positive=True))
    if source["quote_ok"]:
        empty["formation_volume"] = _log_ratio(float(source["quote_sum"]), _priors(rows, source_key, "quote_sum", positive=True))
    high, low, close = float(source["high"]), float(source["low"]), float(source["close"])
    span = high - low
    if math.isfinite(span) and span > 0 and math.isfinite(close):
        if side > 0:
            empty["close_off_extreme"] = (high - close) / span
        else:
            empty["close_off_extreme"] = (close - low) / span
    first, last = int(source["first"]), int(source["last"])
    if last < first:
        return empty
    hh = bars.high[first:last + 1]
    ll = bars.low[first:last + 1]
    ok = np.isfinite(hh) & np.isfinite(ll)
    if side > 0:
        near = ok & (hh >= high * (1.0 - K.EXTREME_TOL))
    else:
        near = ok & (ll <= low * (1.0 + K.EXTREME_TOL))
    idx = np.flatnonzero(near)
    n_ok = int(ok.sum())
    if idx.size and last > first:
        empty["extreme_timing"] = float(idx[-1]) / float(last - first)
    elif idx.size:
        empty["extreme_timing"] = 0.0
    if n_ok:
        empty["extreme_density"] = float(idx.size) / float(n_ok)
    return empty
