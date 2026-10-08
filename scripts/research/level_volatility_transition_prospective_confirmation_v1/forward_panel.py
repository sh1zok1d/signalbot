"""Outcome-blind binding of the prospective forward panel to the live collection.

Owner go 2026-10-08 (`docs/research/LEVEL_VOLATILITY_TRANSITION_PROSPECTIVE_PANEL_BINDING_V1.md`).

Source: the Signalbot Stage-1 collection, table `klines_1m`, exchange `binance`, symbol
`BTCUSDT` (Binance USD-M perpetual), read-only. `ts` is the open time of the minute. Closed
minutes become complete UTC 5m bins through `scripts.research.dh1.data.aggregate_1m_to_5m`;
nothing is filled.

What it reports: rows and minutes present, missing post-start minutes, incomplete post-start
5m bins, and the structural episodes and real first touches that the frozen #352 constructor
finds after the start, by family and structural side. It computes no RV, no transition, no
barrier label and no pseudo touch. It does not import the claim or the evaluator.
"""

from __future__ import annotations

import datetime as dt
from collections import Counter

import numpy as np

from scripts.research.dh1.data import aggregate_1m_to_5m, to_bars
from scripts.research.level_touch_degradation_v1 import constants as PARENT

from . import events
from .surface import UTC, parse_utc, to_iso, to_ms

SOURCE_TABLE = "klines_1m"
SOURCE_EXCHANGE = "binance"
SOURCE_SYMBOL = "BTCUSDT"
MINUTE_MS = 60_000
# First day of the month before the prospective start: October's month levels need September.
# Warm-up only (PRE_START_DATA_ROLE); it lies after the E1-RUN-001 holdout.
WARMUP_START_UTC = "2026-09-01T00:00:00Z"
MAX_LISTED_GAPS = 50

_QUERY = (
    "SELECT ts, open, high, low, close, volume, source FROM klines_1m "
    "WHERE exchange = $1 AND symbol = $2 AND ts >= $3 AND ts < $4 ORDER BY ts"
)


def warmup_start_ms() -> int:
    return to_ms(parse_utc(WARMUP_START_UTC))


def assert_outside_e1(t_ms: np.ndarray) -> None:
    inside = (t_ms >= PARENT.E1_START_MS) & (t_ms < PARENT.E1_END_MS)
    if np.any(inside):
        raise RuntimeError("forward panel overlaps the E1-RUN-001 holdout")


def closed_minutes(rows: list[dict], now_ms: int) -> dict:
    """Closed 1m rows as arrays. A minute is closed when its open time + 1m <= now."""
    keep = [r for r in rows if to_ms(r["ts"]) + MINUTE_MS <= int(now_ms)]
    t = np.array([to_ms(r["ts"]) for r in keep], dtype=np.int64)
    if t.size and np.any(np.diff(t) <= 0):
        raise RuntimeError("1m open times not strictly increasing")
    assert_outside_e1(t)

    def col(name: str) -> np.ndarray:
        return np.array([float(r[name]) for r in keep], dtype=float)

    return {
        "t": t,
        "open": col("open"),
        "high": col("high"),
        "low": col("low"),
        "close": col("close"),
        "volume": col("volume"),
        "sources": dict(Counter(str(r.get("source") or "unknown") for r in keep)),
    }


def _gap_runs(missing: np.ndarray) -> list[dict]:
    if missing.size == 0:
        return []
    breaks = np.flatnonzero(np.diff(missing) != MINUTE_MS)
    starts = np.r_[0, breaks + 1]
    ends = np.r_[breaks, missing.size - 1]
    out = []
    for s, e in zip(starts, ends):
        lo, hi = int(missing[s]), int(missing[e]) + MINUTE_MS
        out.append({
            "from": to_iso(dt.datetime.fromtimestamp(lo / 1000, UTC)),
            "to": to_iso(dt.datetime.fromtimestamp(hi / 1000, UTC)),
            "minutes": int((hi - lo) // MINUTE_MS),
        })
    return out


def post_start_coverage(t: np.ndarray, start_ms: int, now_ms: int) -> dict:
    """Presence only, from the start to the last closed minute and the last closed 5m bin."""
    end_min = (int(now_ms) // MINUTE_MS) * MINUTE_MS
    end_5m = (int(now_ms) // PARENT.BAR_MS) * PARENT.BAR_MS
    if end_min <= int(start_ms):
        return {"expected_minutes": 0, "present_minutes": 0, "missing_minutes": 0,
                "expected_5m_bins": 0, "incomplete_5m_bins": 0, "missing_runs": [],
                "missing_runs_truncated": False}
    grid = np.arange(int(start_ms), end_min, MINUTE_MS, dtype=np.int64)
    present = np.isin(grid, t)
    missing = grid[~present]
    runs = _gap_runs(missing)
    bins = np.arange(int(start_ms), max(int(start_ms), end_5m), PARENT.BAR_MS, dtype=np.int64)
    in_window = t[(t >= int(start_ms)) & (t < end_5m)]
    per_bin = Counter(((in_window // PARENT.BAR_MS) * PARENT.BAR_MS).tolist())
    incomplete = int(sum(1 for b in bins.tolist() if per_bin.get(b, 0) != 5))
    return {
        "expected_minutes": int(grid.size),
        "present_minutes": int(present.sum()),
        "missing_minutes": int(missing.size),
        "expected_5m_bins": int(bins.size),
        "incomplete_5m_bins": incomplete,
        "missing_runs": runs[:MAX_LISTED_GAPS],
        "missing_runs_truncated": len(runs) > MAX_LISTED_GAPS,
    }


def panel_bars(m: dict, now_ms: int):
    """Contiguous 5m grid from the warm-up start to the last closed 5m bin; gaps stay NaN."""
    start = warmup_start_ms()
    end = (int(now_ms) // PARENT.BAR_MS) * PARENT.BAR_MS
    if end <= start:
        raise RuntimeError("no closed 5m bar after the warm-up start")
    zeros = np.zeros_like(m["close"])
    panel = aggregate_1m_to_5m(m["t"], m["open"], m["high"], m["low"], m["close"], m["volume"],
                               zeros, zeros)
    panel = {k: v[panel["open_ms"] + PARENT.BAR_MS <= end] for k, v in panel.items()}
    return to_bars(panel, start, end), end


def structural_counts(bars, start_ms: int, end_ms: int) -> dict:
    """Eligible real episodes and touch-1 events. No resolution label is read."""
    if int(end_ms) <= int(start_ms):
        return {"structural_episodes": 0, "real_first_touches": 0, "family_counts": {},
                "side_counts": {}}
    episodes, _instances, _info = events.prospective_episodes(bars, int(start_ms))
    touches = events.first_touches(bars, episodes, end_ms=int(end_ms))
    side_name = {1: "resistance", -1: "support"}
    return {
        "structural_episodes": len(episodes),
        "real_first_touches": len(touches),
        "family_counts": dict(sorted(Counter(str(t["family"]) for t in touches).items())),
        "side_counts": dict(sorted(Counter(side_name.get(int(t["struct_side"]), "unknown")
                                           for t in touches).items())),
    }


def bind(rows: list[dict], *, start_ms: int, now: dt.datetime) -> dict:
    """Status inputs and the panel block from closed rows. Outcome-blind."""
    now_ms = to_ms(now)
    m = closed_minutes(rows, now_ms)
    if m["t"].size == 0:
        raise RuntimeError("the live collection returned no closed BTCUSDT minute")
    bars, end_ms = panel_bars(m, now_ms)
    counts = structural_counts(bars, start_ms, end_ms)
    coverage = post_start_coverage(m["t"], start_ms, now_ms)
    last_open = int(m["t"][-1])
    panel = {
        "source": f"{SOURCE_TABLE} exchange={SOURCE_EXCHANGE} symbol={SOURCE_SYMBOL} (read-only)",
        "aggregation": "scripts.research.dh1.data.aggregate_1m_to_5m; complete 5m bins only",
        "warmup_start": WARMUP_START_UTC,
        "rows_read": int(m["t"].size),
        "rows_by_source": m["sources"],
        "first_minute": to_iso(dt.datetime.fromtimestamp(int(m["t"][0]) / 1000, UTC)),
        "last_closed_minute": to_iso(dt.datetime.fromtimestamp(last_open / 1000, UTC)),
        "last_minute_age_s": int((now_ms - (last_open + MINUTE_MS)) // 1000),
        "post_start_coverage": coverage,
    }
    return {"counts": counts, "gaps": coverage["incomplete_5m_bins"], "panel": panel}


async def fetch_rows(dsn: str, *, now: dt.datetime) -> list[dict]:
    """Read the warm-up and forward minutes in a read-only transaction."""
    import asyncpg

    conn = await asyncpg.connect(dsn)
    try:
        async with conn.transaction(readonly=True):
            rows = await conn.fetch(
                _QUERY, SOURCE_EXCHANGE, SOURCE_SYMBOL,
                parse_utc(WARMUP_START_UTC), now.astimezone(UTC))
    finally:
        await conn.close()
    return [dict(r) for r in rows]
