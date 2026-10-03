"""Nightly statistics build for decision support (PRODUCT_DECISION_V2 §2, §7).

    main.py --beta-history-build

Reads the Binance history (`beta_hist_bars_5m`, `beta_hist_oi_5m`) month by month into one 5m
grid, fits the range model, measures level reactions, labels the 1h / 4h states and measures
event days, then appends ONE `beta_hist_stats` row. The product always reads the newest row;
a failed build leaves the previous row in place.
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping, Optional

import numpy as np

from .config import BetaConfig
from .hist_series import BAR_MS, Bars, empty_bars, floor_bar, to_ms

logger = logging.getLogger("beta.history_stats")

HIST_STATS_VERSION = "BETA_HIST_STATS_V1"
MIN_HISTORY_DAYS = 120


def json_safe(obj):
    """NaN / inf → None, numpy scalars → Python, tuples → lists (the store rejects NaN)."""
    if isinstance(obj, dict):
        return {str(k): json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [json_safe(v) for v in obj]
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (float, np.floating)):
        f = float(obj)
        return f if np.isfinite(f) else None
    if isinstance(obj, np.bool_):
        return bool(obj)
    return obj


def build_stats_payload(b: Bars, *, cfg: BetaConfig, calendar: Mapping[str, Any]) -> dict:
    """Every statistic from one grid. Pure (no I/O)."""
    from .analogues import analogue_stats
    from .calendar_events import event_size_stats, event_times_ms
    from .levels import level_reaction_stats
    from .rangecast import fit_range_model
    timings = {}
    t = time.monotonic()
    events = event_times_ms(calendar)
    model = fit_range_model(b, events=events)
    timings["range_model_s"] = round(time.monotonic() - t, 2)
    t = time.monotonic()
    levels = level_reaction_stats(b)
    timings["levels_s"] = round(time.monotonic() - t, 2)
    t = time.monotonic()
    analogues = analogue_stats(b, context=cfg.section("context")) if np.isfinite(b.oi).any() else \
        {"version": None, "windows": {}, "reason": "NO_OI_HISTORY"}
    timings["analogues_s"] = round(time.monotonic() - t, 2)
    t = time.monotonic()
    ev = event_size_stats(b, calendar)
    timings["events_s"] = round(time.monotonic() - t, 2)
    present = b.present()
    first = int(np.flatnonzero(present)[0]) if present.any() else 0
    last = int(np.flatnonzero(present)[-1]) if present.any() else 0
    oi_idx = np.flatnonzero(np.isfinite(b.oi))
    return json_safe({"version": HIST_STATS_VERSION, "source": "binance_usdm_btcusdt_5m (data.binance.vision)",
            "data": {"from_ms": int(b.t0 + first * BAR_MS), "to_ms": int(b.t0 + (last + 1) * BAR_MS),
                     "bars": int(present.sum()), "missing_bars": int((~present[first:last + 1]).sum()),
                     "oi_from_ms": int(b.t0 + oi_idx[0] * BAR_MS) if oi_idx.size else None,
                     "calendar_version": calendar.get("version")},
            "range_model": model, "levels": levels, "analogues": analogues, "events": ev,
            "timings": timings})


async def load_history_grid(conn, *, start: datetime, end: datetime) -> Bars:
    """The 5m grid [start, end) filled month by month (bounded memory)."""
    t0 = floor_bar(to_ms(start))
    n = (floor_bar(to_ms(end) - 1) - t0) // BAR_MS + 1
    b = empty_bars(t0, max(0, n))
    cur = start
    while cur < end:
        nxt = min(end, (cur.replace(day=1) + timedelta(days=32)).replace(day=1, hour=0, minute=0,
                                                                         second=0, microsecond=0))
        for r in await conn.fetch_hist_bars(start=cur, end=nxt):
            i = (int(r["open_time_ms"]) - t0) // BAR_MS
            if 0 <= i < b.n:
                b.open[i], b.high[i], b.low[i], b.close[i] = r["open"], r["high"], r["low"], r["close"]
                b.volume[i] = np.nan if r["volume"] is None else r["volume"]
                b.quote[i] = np.nan if r["quote_volume"] is None else r["quote_volume"]
                b.taker_buy_quote[i] = np.nan if r["taker_buy_quote"] is None else r["taker_buy_quote"]
        for r in await conn.fetch_hist_oi(start=cur, end=nxt):
            i = (int(r["ts_ms"]) - t0) // BAR_MS
            if 0 <= i < b.n:
                b.oi[i] = r["oi"]
        cur = nxt
    return b


async def run_history_build(store, cfg: BetaConfig, *, now: datetime,
                            calendar: Optional[Mapping[str, Any]] = None) -> dict:
    from storage.beta_v0_store import HISTORY_LOCK_KEY
    from .calendar_events import load_calendar
    calendar = calendar or load_calendar()
    async with store.advisory_lock(HISTORY_LOCK_KEY) as acquired:
        if not acquired:
            return {"status": "BUSY"}
        try:
            async with store.connect() as conn:
                bounds = await conn.hist_bounds()
                if bounds["bars_from"] is None:
                    return {"status": "NO_HISTORY", "hint": "run --beta-history-sync first"}
                end = min(bounds["bars_through"] + timedelta(minutes=5),
                          now.astimezone(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0))
                start = bounds["bars_from"]
                if (end - start).days < MIN_HISTORY_DAYS:
                    return {"status": "NOT_ENOUGH_HISTORY", "days": (end - start).days}
                b = await load_history_grid(conn, start=start, end=end)
            payload = build_stats_payload(b, cfg=cfg, calendar=calendar)
            async with store.connect() as conn:
                pk = await conn.insert_hist_stats(
                    version=HIST_STATS_VERSION, built_at=now, data_from=start, data_through=end,
                    payload=payload)
                await conn.record_health("history_build", now=datetime.now(timezone.utc), success=True,
                                         detail={"stats_pk": pk, **payload["timings"]})
            cal = (payload["range_model"].get("calibration") or {})
            return {"status": "OK", "stats_pk": pk, "data_from": start, "data_through": end,
                    "bars": payload["data"]["bars"], "missing_bars": payload["data"]["missing_bars"],
                    "timings": payload["timings"],
                    "corridor_coverage_holdout": {h: c.get("coverage_realized") for h, c in cal.items()},
                    "level_family": payload["levels"].get("family_size"),
                    "analogue_family": payload["analogues"].get("family_size")}
        except Exception as exc:
            logger.warning("history build failed: %s", type(exc).__name__)
            async with store.connect() as conn:
                await conn.record_health("history_build", now=datetime.now(timezone.utc), success=False,
                                         error_type=type(exc).__name__)
            raise
