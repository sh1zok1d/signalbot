"""Load the pinned OKX funding extract and the same-venue 5-minute path.

Outcome statistics are not computed here. Open interest is not opened.
"""

from __future__ import annotations

import datetime as dt
import gzip
import hashlib
import json
from pathlib import Path

import numpy as np

from scripts.research.funding_state_historical_structure_v1.model import (
    absolute_excursion,
    adverse_long,
    funding_state,
)

from . import constants as K
from .model import decision_time, extremity, upside

ROOT = Path(__file__).resolve().parents[3]
FUNDING_PATH = (
    ROOT
    / "docs"
    / "research_data"
    / "OKX_BTC_USDT_SWAP_FUNDING_ARCHIVE_V1"
    / "btc_usdt_swap_funding.json"
)
SOURCE_ZIPS_PATH = (
    ROOT
    / "docs"
    / "research_data"
    / "OKX_BTC_USDT_SWAP_FUNDING_ARCHIVE_V1"
    / "source_zips.json"
)
PRICE_PATH = (
    ROOT
    / "docs"
    / "research_data"
    / "LEVEL_CROSS_VENUE_PERP_5M_V0"
    / "okx_btc_usdt_swap_5m.csv.gz"
)
UTC = dt.timezone.utc


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Bars:
    def __init__(self, times: np.ndarray, high: np.ndarray, low: np.ndarray, close: np.ndarray):
        self.times = times
        self.high = high
        self.low = low
        self.close = close
        self.n = int(times.size)

    def index_at_open(self, open_ms: int) -> int:
        idx = int(np.searchsorted(self.times, int(open_ms)))
        if idx >= self.n or int(self.times[idx]) != int(open_ms):
            return -1
        return idx


def load_funding() -> tuple[np.ndarray, np.ndarray]:
    if _sha256(FUNDING_PATH) != K.FUNDING_SHA256:
        raise SystemExit("FUNDING_DIGEST_MISMATCH")
    if _sha256(SOURCE_ZIPS_PATH) != K.SOURCE_ZIPS_SHA256:
        raise SystemExit("SOURCE_ZIPS_DIGEST_MISMATCH")
    rows = json.loads(FUNDING_PATH.read_text(encoding="utf-8"))
    times = np.asarray([int(row["funding_time"]) for row in rows], dtype=np.int64)
    rates = np.asarray([float(row["funding_rate"]) for row in rows], dtype=np.float64)
    if times.size != K.FUNDING_N:
        raise SystemExit(f"SAMPLE_DOES_NOT_MATCH_AUDIT n={times.size}")
    if int(times[0]) != K.FIRST_FUNDING_MS or int(times[-1]) != K.LAST_FUNDING_MS:
        raise SystemExit("SAMPLE_DOES_NOT_MATCH_AUDIT bounds")
    if not np.all(times[1:] > times[:-1]):
        raise SystemExit("FUNDING_TIMES_NOT_STRICTLY_INCREASING")
    if int(np.sum(times >= K.SURFACE_END_MS)) != 0:
        raise SystemExit("FUNDING_TOUCHES_2025")
    if int(np.sum(times == K.OFF_GRID_MS)) != 1 or int(np.sum(times == K.ONE_SECOND_MS)) != 1:
        raise SystemExit("SAMPLE_DOES_NOT_MATCH_AUDIT schedule marks")
    on_grid = 0
    off_grid = 0
    for stamp in times.tolist():
        if decision_time(int(stamp)) is None:
            off_grid += 1
        else:
            on_grid += 1
    if off_grid != K.OFF_GRID_N or on_grid != K.ON_GRID_N:
        raise SystemExit(f"SAMPLE_DOES_NOT_MATCH_AUDIT grid {on_grid} {off_grid}")
    return times, rates


def load_price() -> Bars:
    if _sha256(PRICE_PATH) != K.PRICE_SHA256:
        raise SystemExit("PRICE_DIGEST_MISMATCH")
    opens: list[int] = []
    highs: list[float] = []
    lows: list[float] = []
    closes: list[float] = []
    with gzip.open(PRICE_PATH, "rt") as handle:
        header = handle.readline().strip()
        if header != "open_ms,open,high,low,close":
            raise SystemExit("PRICE_HEADER")
        for line in handle:
            parts = line.strip().split(",")
            if len(parts) != 5:
                raise SystemExit("PRICE_SHORT_ROW")
            opens.append(int(parts[0]))
            highs.append(float(parts[2]))
            lows.append(float(parts[3]))
            closes.append(float(parts[4]))
    times = np.asarray(opens, dtype=np.int64)
    if times.size != K.PRICE_N:
        raise SystemExit(f"SAMPLE_DOES_NOT_MATCH_AUDIT price n={times.size}")
    if int(times[0]) != K.PRICE_FIRST_MS or int(times[-1]) != K.PRICE_LAST_MS:
        raise SystemExit("SAMPLE_DOES_NOT_MATCH_AUDIT price bounds")
    if not np.all(np.diff(times) > 0):
        raise SystemExit("PRICE_TIMES_NOT_STRICTLY_INCREASING")
    if int(np.sum(times % K.BAR_MS != 0)) != 0:
        raise SystemExit("PRICE_OFF_GRID")
    if int(np.sum(times >= K.SURFACE_END_MS)) != 0:
        raise SystemExit("PRICE_TOUCHES_2025")
    expected = (int(times[-1]) - int(times[0])) // K.BAR_MS + 1
    if expected != int(times.size):
        raise SystemExit(f"PRICE_GAPS {expected - int(times.size)}")
    return Bars(times, np.asarray(highs), np.asarray(lows), np.asarray(closes))


def _window(bars: Bars, start_open: int, n_bars: int):
    i0 = bars.index_at_open(start_open)
    i1 = i0 + n_bars
    if i0 < 0 or i1 > bars.n:
        return None
    if int(bars.times[i0]) != start_open:
        return None
    if int(bars.times[i1 - 1]) >= K.SURFACE_END_MS:
        return None
    return i0, i1


def math_sqrt_sumsq(rets: np.ndarray) -> float:
    return float(np.sqrt(np.dot(rets, rets)))


def build_frame() -> dict:
    funding_time, rate = load_funding()
    bars = load_price()
    state = funding_state(rate, min_past=K.MIN_PAST)
    kept = {
        "t": [],
        "rate": [],
        "rank": [],
        "extremity": [],
        "rv": [],
        "abs_excursion": [],
        "downside": [],
        "upside": [],
        "year": [],
        "week": [],
    }
    dropped = {"schedule_exception": 0, "state_undefined": 0, "path": 0, "rv": 0}
    for i, raw_t in enumerate(funding_time.tolist()):
        decided = decision_time(int(raw_t))
        if decided is None:
            dropped["schedule_exception"] += 1
            continue
        if not np.isfinite(state[i]):
            dropped["state_undefined"] += 1
            continue
        t = int(decided)
        p0_open = t - K.BAR_MS
        p0_slice = _window(bars, p0_open, 1)
        future = _window(bars, t, K.PRIMARY_BARS)
        rv_open = t - K.RV_RETURNS * K.BAR_MS - K.BAR_MS
        rv_slice = _window(bars, rv_open, K.RV_RETURNS + 1)
        if p0_slice is None or future is None or rv_slice is None:
            dropped["path"] += 1
            continue
        p0 = float(bars.close[p0_slice[0]])
        closes = bars.close[rv_slice[0]:rv_slice[1]]
        lows = bars.low[future[0]:future[1]]
        highs = bars.high[future[0]:future[1]]
        if not np.all(np.isfinite(closes)) or np.any(closes <= 0.0):
            dropped["rv"] += 1
            continue
        rets = np.log(closes[1:] / closes[:-1])
        if rets.size != K.RV_RETURNS or not np.all(np.isfinite(rets)):
            dropped["rv"] += 1
            continue
        try:
            excursion = absolute_excursion(p0, lows, highs)
            down = adverse_long(p0, lows)
            up = upside(p0, highs)
        except RuntimeError:
            dropped["path"] += 1
            continue
        stamp = dt.datetime.fromtimestamp(t / 1000.0, tz=UTC)
        iso = stamp.isocalendar()
        kept["t"].append(t)
        kept["rate"].append(float(rate[i]))
        kept["rank"].append(float(state[i]))
        kept["extremity"].append(float(extremity(np.asarray([state[i]]))[0]))
        kept["rv"].append(math_sqrt_sumsq(rets))
        kept["abs_excursion"].append(excursion)
        kept["downside"].append(down)
        kept["upside"].append(up)
        kept["year"].append(stamp.year)
        kept["week"].append((int(iso[0]), int(iso[1])))
    frame = {key: np.asarray(value) if key != "week" else value for key, value in kept.items()}
    frame["dropped"] = dropped
    frame["funding_n"] = int(funding_time.size)
    return frame
