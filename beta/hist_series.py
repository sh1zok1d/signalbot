"""A contiguous 5m bar grid for the decision-support statistics (PRODUCT_DECISION_V2 §2).

One venue: Binance USD-M BTCUSDT. Index i is the bar that opens at t0 + i*5m and closes
at t0 + (i+1)*5m. A missing bar is NaN in every column; nothing is forward-filled.

`oi[i]` is the Binance open interest (base BTC) of the Vision `metrics` snapshot labelled
with bar i's open time. Under the conservative CORE rule that snapshot is usable at the
bar's close, so `oi[i]` is the OI known at the close of bar i.

Pure numpy / pandas; no I/O.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable, Mapping, Optional, Sequence

import numpy as np
import pandas as pd

BAR_MS = 300_000
BARS_PER_HOUR = 12
BARS_PER_DAY = 288
COLUMNS = ("open", "high", "low", "close", "volume", "quote", "taker_buy_quote")


def to_ms(dt: datetime) -> int:
    if dt.tzinfo is None:
        raise ValueError("timestamps must be timezone-aware")
    return int(round(dt.timestamp() * 1000))


def from_ms(ms: int) -> datetime:
    return datetime.fromtimestamp(int(ms) / 1000.0, tz=timezone.utc)


def floor_bar(ms: int) -> int:
    return int(ms) - int(ms) % BAR_MS


@dataclass
class Bars:
    t0: int
    open: np.ndarray
    high: np.ndarray
    low: np.ndarray
    close: np.ndarray
    volume: np.ndarray
    quote: np.ndarray
    taker_buy_quote: np.ndarray
    oi: np.ndarray

    @property
    def n(self) -> int:
        return int(self.close.shape[0])

    @property
    def times(self) -> np.ndarray:
        """Open time (ms) of every bar."""
        return self.t0 + np.arange(self.n, dtype=np.int64) * BAR_MS

    @property
    def end_ms(self) -> int:
        """Close time of the last bar."""
        return self.t0 + self.n * BAR_MS

    def index_at_open(self, ms: int) -> int:
        return (int(ms) - self.t0) // BAR_MS

    def present(self) -> np.ndarray:
        return np.isfinite(self.close)

    def last_complete_index(self) -> Optional[int]:
        idx = np.flatnonzero(self.present())
        return int(idx[-1]) if idx.size else None

    def tail(self, n: int) -> "Bars":
        n = min(int(n), self.n)
        start = self.n - n
        return self.slice(start, self.n)

    def slice(self, a: int, b: int) -> "Bars":
        a, b = max(0, int(a)), min(self.n, int(b))
        return Bars(t0=self.t0 + a * BAR_MS, **{c: getattr(self, c)[a:b].copy() for c in COLUMNS},
                    oi=self.oi[a:b].copy())


def empty_bars(t0: int, n: int) -> Bars:
    nan = lambda: np.full(n, np.nan)  # noqa: E731
    return Bars(t0=t0, open=nan(), high=nan(), low=nan(), close=nan(), volume=nan(), quote=nan(),
                taker_buy_quote=nan(), oi=nan())


def bars_from_rows(rows: Iterable[Mapping], *, oi_rows: Iterable[Mapping] = (),
                   start_ms: Optional[int] = None, end_ms: Optional[int] = None) -> Bars:
    """Build the grid from bar rows ({open_time_ms|open_time, open, high, low, close, volume,
    quote_volume, taker_buy_quote}) and optional OI rows ({ts_ms|ts, oi}). `end_ms` is exclusive
    (a bar opening at end_ms is not included)."""
    rows = list(rows)
    times = [_row_ms(r, "open_time") for r in rows]
    if start_ms is None:
        start_ms = min(times) if times else 0
    start_ms = floor_bar(start_ms)
    if end_ms is None:
        end_ms = (max(times) + BAR_MS) if times else start_ms
    n = max(0, (floor_bar(int(end_ms) - 1) - start_ms) // BAR_MS + 1) if end_ms > start_ms else 0
    b = empty_bars(start_ms, n)
    for r, ms in zip(rows, times):
        i = (ms - start_ms) // BAR_MS
        if ms % BAR_MS or not 0 <= i < n:
            continue
        b.open[i] = float(r["open"])
        b.high[i] = float(r["high"])
        b.low[i] = float(r["low"])
        b.close[i] = float(r["close"])
        b.volume[i] = _f(r.get("volume"))
        b.quote[i] = _f(r.get("quote_volume", r.get("quote")))
        b.taker_buy_quote[i] = _f(r.get("taker_buy_quote"))
    for r in oi_rows:
        ms = _row_ms(r, "ts")
        i = (ms - start_ms) // BAR_MS
        if ms % BAR_MS or not 0 <= i < n:
            continue
        b.oi[i] = _f(r.get("oi", r.get("oi_base")))
    return b


def _row_ms(r: Mapping, key: str) -> int:
    v = r.get(key + "_ms")
    if v is not None:
        return int(v)
    v = r[key]
    return to_ms(v) if isinstance(v, datetime) else int(v)


def _f(v) -> float:
    return np.nan if v is None else float(v)


def aggregate_1m(rows_1m: Iterable[Mapping], *, require_all: bool = True) -> list:
    """Live Stage-1 1m klines (ts, open, high, low, close, volume, taker_buy_volume) → 5m rows.
    A 5m bar needs all five 1m bars when `require_all`. Quote volume and taker-buy quote are
    approximated with each minute's close (Stage-1 stores base volume only)."""
    groups: dict = {}
    for r in rows_1m:
        ms = _row_ms(r, "ts")
        groups.setdefault(floor_bar(ms), []).append((ms, r))
    out = []
    for start in sorted(groups):
        members = sorted(groups[start], key=lambda x: x[0])
        if require_all and len(members) != 5:
            continue
        rs = [m[1] for m in members]
        vol = sum(float(r.get("volume") or 0.0) for r in rs)
        quote = sum(float(r.get("volume") or 0.0) * float(r["close"]) for r in rs)
        tb = [r.get("taker_buy_volume") for r in rs]
        tbq = (sum(float(v) * float(r["close"]) for v, r in zip(tb, rs))
               if all(v is not None for v in tb) else None)
        out.append({"open_time_ms": start, "open": float(rs[0]["open"]), "close": float(rs[-1]["close"]),
                    "high": max(float(r["high"]) for r in rs), "low": min(float(r["low"]) for r in rs),
                    "volume": vol, "quote_volume": quote, "taker_buy_quote": tbq})
    return out


def merge_rows(history: Sequence[Mapping], live: Sequence[Mapping]) -> list:
    """History rows win where they exist; live rows only fill bars after the last history bar."""
    hist = list(history)
    last = max((_row_ms(r, "open_time") for r in hist), default=None)
    tail = [r for r in live if last is None or _row_ms(r, "open_time") > last]
    return hist + tail


# ---- rolling helpers (pandas, O(N)) --------------------------------------------------
def rolling_max(a: np.ndarray, n: int, *, min_frac: float = 0.9) -> np.ndarray:
    return pd.Series(a).rolling(int(n), min_periods=max(1, int(np.ceil(n * min_frac)))).max().to_numpy()


def rolling_min(a: np.ndarray, n: int, *, min_frac: float = 0.9) -> np.ndarray:
    return pd.Series(a).rolling(int(n), min_periods=max(1, int(np.ceil(n * min_frac)))).min().to_numpy()


def rolling_sum(a: np.ndarray, n: int) -> np.ndarray:
    """Strict: a window with any missing value is NaN."""
    return pd.Series(a).rolling(int(n), min_periods=int(n)).sum().to_numpy()


def forward_extremes(b: Bars, h: int, *, min_frac: float = 0.9) -> tuple:
    """(max high, min low, close) over bars i+1 .. i+h, for every i. NaN where unknown."""
    hi = rolling_max(b.high, h, min_frac=min_frac)
    lo = rolling_min(b.low, h, min_frac=min_frac)
    fwd_hi = np.full(b.n, np.nan)
    fwd_lo = np.full(b.n, np.nan)
    fwd_close = np.full(b.n, np.nan)
    if b.n > h:
        fwd_hi[:-h] = hi[h:]
        fwd_lo[:-h] = lo[h:]
        fwd_close[:-h] = b.close[h:]
    return fwd_hi, fwd_lo, fwd_close


def past_range_pct(b: Bars, n: int, *, min_frac: float = 0.9) -> np.ndarray:
    """(max high − min low) over bars i−n+1 .. i, in % of close[i]."""
    hi = rolling_max(b.high, n, min_frac=min_frac)
    lo = rolling_min(b.low, n, min_frac=min_frac)
    with np.errstate(invalid="ignore", divide="ignore"):
        return (hi - lo) / b.close * 100.0


def utc_hour(times_ms: np.ndarray) -> np.ndarray:
    return ((np.asarray(times_ms, dtype=np.int64) // 3_600_000) % 24).astype(np.int64)


def utc_weekday(times_ms: np.ndarray) -> np.ndarray:
    """Monday = 0 … Sunday = 6 (1970-01-01 was a Thursday)."""
    return ((np.asarray(times_ms, dtype=np.int64) // 86_400_000 + 3) % 7).astype(np.int64)
