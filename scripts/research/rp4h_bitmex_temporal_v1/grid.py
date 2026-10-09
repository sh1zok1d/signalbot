"""BitMEX canonical 5m series on the clock grid. Canonical missingness: zero-trade buckets are bars; absent timestamps are holes."""

from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path

import numpy as np

from . import constants as K

ROOT = Path(__file__).resolve().parents[3]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_rows(lines) -> dict:
    """Every canonical row is a bar, zero-trade buckets included (OHLC exactly as published)."""
    opens, highs, lows, closes, trades = [], [], [], [], []
    for line in lines:
        r = json.loads(line)
        vals = [r.get(k) for k in ("open", "high", "low", "close")]
        if any(v is None for v in vals):
            raise SystemExit("SERIES_NULL_PRICE")
        opens.append(int(r["open_time_ms"]))
        highs.append(float(r["high"]))
        lows.append(float(r["low"]))
        closes.append(float(r["close"]))
        trades.append(int(r["trades"]))
    return {"open_ms": np.asarray(opens, dtype=np.int64), "high": np.asarray(highs), "low": np.asarray(lows),
            "close": np.asarray(closes), "trades": np.asarray(trades, dtype=np.int64)}


def load_series() -> dict:
    path = ROOT / K.SERIES
    if sha256(path) != K.SERIES_SHA256:
        raise SystemExit("SERIES_HASH_MISMATCH")
    with gzip.open(path, "rt") as handle:
        return parse_rows(handle)


def missing_opens(open_ms: np.ndarray) -> np.ndarray:
    """Clock slots between the first and the last open with no row."""
    if np.any(np.diff(open_ms) <= 0):
        raise SystemExit("OPEN_TIMES_NOT_INCREASING")
    if np.any(open_ms % K.BAR_MS != 0):
        raise SystemExit("OPEN_TIMES_OFF_GRID")
    full = np.arange(open_ms[0], open_ms[-1] + K.BAR_MS, K.BAR_MS, dtype=np.int64)
    return np.setdiff1d(full, open_ms, assume_unique=True)


def preflight_census(series: dict) -> dict:
    """Refuses unless the bounds and the one documented gap match the source authority exactly."""
    t = series["open_ms"]
    if int(t[0]) != K.FIRST_OPEN_MS or int(t[-1]) != K.LAST_OPEN_MS or int(t[-1]) >= K.SURFACE_END_MS:
        raise SystemExit("SERIES_BOUNDS")
    gaps = missing_opens(t)
    expected = np.arange(K.GAP_FIRST_OPEN_MS, K.GAP_LAST_OPEN_MS + K.BAR_MS, K.BAR_MS, dtype=np.int64)
    if gaps.size != K.GAP_COUNT or not np.array_equal(gaps, expected):
        raise SystemExit("GAP_CENSUS_MISMATCH")
    auth = json.loads((ROOT / K.AUTHORITY).read_text())
    if auth["canonical_jsonl_gz_sha256"] != K.SERIES_SHA256 or auth["gaps"]["missing_bucket_count"] != K.GAP_COUNT:
        raise SystemExit("AUTHORITY_MISMATCH")
    if not auth["coverage"]["zero_trade_buckets_retained_as_official_source_bins"]:
        raise SystemExit("AUTHORITY_MISSINGNESS_CHANGED")
    return {"rows": int(t.size), "holes": int(gaps.size), "zero_trade_bars": int((series["trades"] == 0).sum()),
            "first_open_ms": int(t[0]), "last_open_ms": int(t[-1])}


def place(series: dict) -> dict:
    """Put bars on the complete 5m grid from the first open to the last. Holes stay NaN; nothing is filled."""
    t = series["open_ms"]
    n = int((t[-1] - t[0]) // K.BAR_MS + 1)
    slot = (t - t[0]) // K.BAR_MS
    out = {"grid_open": t[0] + np.arange(n, dtype=np.int64) * K.BAR_MS, "slots": n, "occupied": int(t.size),
           "holes": int(n - t.size)}
    for c in ("high", "low", "close"):
        arr = np.full(n, np.nan)
        arr[slot] = series[c]
        out[c] = arr
    return out


def anchor_mask(grid_open: np.ndarray) -> np.ndarray:
    """Parent phase on the clock (floor modulo from 2020-01-01): bar opens at minute 10 mod 15; T before 2020."""
    idx = (grid_open - K.PHASE_ORIGIN_MS) // K.BAR_MS
    return ((idx % 3) == 2) & (grid_open + K.BAR_MS < K.SURFACE_END_MS)


def local_returns(close: np.ndarray) -> dict:
    """RET_1H and RET_15M at bar i: log(close[i] / close[i-12]) and log(close[i] / close[i-3]). Secondary only."""
    out = {}
    for name, lag in (("ret1h", K.LOCAL_1H), ("ret15", K.LOCAL_15M)):
        arr = np.full(close.size, np.nan)
        with np.errstate(divide="ignore", invalid="ignore"):
            arr[lag:] = np.log(close[lag:] / close[:-lag])
        out[name] = arr
    return out
