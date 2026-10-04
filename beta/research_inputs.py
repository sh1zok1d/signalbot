"""Assemble the research-evidence engine's market state from storage (read-only).

Sources and their rules (docs/research/RESEARCH_EVIDENCE_INTEGRATION_V1.md §3):
- bars: the decision block's own 5m grid (Vision history + the Stage-1 1m tail), unchanged;
- open interest and the global long/short account ratio: Vision `metrics` history wins; the
  public REST tail fills only after the history's end and only once the REST-vs-Vision
  definition check (recorded by the feeds job) is OK; otherwise the tail is not used and the
  findings that need it are unavailable with the reason;
- DVOL, ±1 % depth, spot 5m bars, stress hours: the read-only feed tables;
- taker flow for H05: Stage-1 Binance 1m base volumes summed into complete 15-minute buckets;
- the daily RV series for D2: SQL over `beta_hist_bars_5m`, the newest days from the grid.
A source older than its freshness limit is marked STALE; nothing is filled in.
"""
from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping, Optional

import numpy as np

from . import research_states as RS
from .hist_series import BAR_MS, Bars, from_ms, to_ms
from .research_evidence import EvidenceInputs

HOUR_MS = RS.HOUR_MS
DAY_MS = RS.DAY_MS
FRESH = {"oi": 75 * 60_000, "ls_ratio": 75 * 60_000, "dvol": 75 * 60_000, "depth": 75 * 60_000,
         "spot": 15 * 60_000, "stress": 3 * HOUR_MS, "flow15": 30 * 60_000}
D2_DAYS = 280
_daily_cache: dict = {"day": None, "rows": None}


def _iso(ms: Optional[int]) -> Optional[str]:
    return None if ms is None else from_ms(int(ms)).isoformat()


def _source(present: bool, newest_ms: Optional[int], now_ms: int, limit_ms: Optional[int],
            reason: Optional[str] = None) -> dict:
    if reason is None and present and limit_ms is not None and newest_ms is not None and now_ms - newest_ms > limit_ms:
        reason = "STALE"
    return {"present": bool(present), "as_of": _iso(newest_ms), "reason": reason}


async def _definition(conn) -> dict:
    fetch = getattr(conn, "fetch_health", None)
    if fetch is None:
        return {}
    health = await fetch()
    rec = (health or {}).get("research_feeds_definition") or {}
    return dict(rec.get("detail") or {})


async def _metrics(conn, b: Bars, now: datetime, sources: dict) -> tuple:
    from .history_data import in_protected_window
    start, now_ms = from_ms(b.t0), to_ms(now)
    hist = await conn.fetch_hist_metrics(start=start, end=now)
    feed = await conn.fetch_feed_metrics(start=start, end=now)
    check = await _definition(conn)
    out = []
    for field, name in (("oi_base", "oi"), ("ls_account_ratio", "ls_ratio")):
        h = [(int(r["ts_ms"]), float(r[field])) for r in hist
             if r.get(field) is not None and not in_protected_window(int(r["ts_ms"]))]
        last_h = max((t for t, _ in h), default=None)
        f = [(int(r["ts_ms"]), float(r[field])) for r in feed if r.get(field) is not None
             and (last_h is None or int(r["ts_ms"]) > last_h) and not in_protected_window(int(r["ts_ms"]))]
        status = (check.get(field) or {}).get("status")
        reason = None
        rows = list(h)
        if f and status == "OK":
            rows += f
        elif f:
            reason = "DEFINITION_FAILED" if status == "FAILED" else "DEFINITION_PENDING"
        arr = RS.grid_values(np.array([t for t, _ in rows], dtype=np.int64), np.array([v for _, v in rows]), b.t0, b.n)
        newest = max((t for t, _ in rows), default=None)
        # a label is usable from label + 5m on
        sources[name] = _source(bool(rows), None if newest is None else newest + BAR_MS, now_ms, FRESH[name],
                                reason if (reason and (newest is None or now_ms - (newest + BAR_MS) > 15 * 60_000))
                                else None)
        out.append(arr if rows else None)
    return out[0], out[1]


async def _dvol(conn, now: datetime, sources: dict) -> Optional[dict]:
    rows = await conn.fetch_feed_dvol(start=now - timedelta(days=3), end=now)
    at = {int(r["t_ms"]): float(r["close"]) for r in rows}
    newest = max(at, default=None)
    sources["dvol"] = _source(bool(at), None if newest is None else newest + HOUR_MS, to_ms(now), FRESH["dvol"])
    return at or None


async def _depth(conn, b: Bars, now: datetime, sources: dict) -> Optional[dict]:
    rows = await conn.fetch_feed_depth(start=now - timedelta(days=8), end=now)
    ok = [r for r in rows if r.get("bid1_usd") is not None and r.get("ask1_usd") is not None]
    newest = max((int(r["ts_ms"]) for r in ok), default=None)
    sources["depth"] = _source(bool(ok), newest, to_ms(now), FRESH["depth"],
                               None if ok or not rows else "STALE_OR_NOT_COVERED")
    if not ok:
        return None
    return RS.book_on_grid([int(r["ts_ms"]) for r in ok], [float(r["bid1_usd"]) for r in ok],
                           [float(r["ask1_usd"]) for r in ok], b.t0, b.n)


async def _spot(conn, b: Bars, now: datetime, sources: dict) -> Optional[dict]:
    from .history_data import in_protected_window
    rows = [r for r in await conn.fetch_feed_spot(start=max(from_ms(b.t0), now - timedelta(days=3)), end=now)
            if not in_protected_window(int(r["open_time_ms"]))]
    newest = max((int(r["open_time_ms"]) + BAR_MS for r in rows), default=None)
    sources["spot"] = _source(bool(rows), newest, to_ms(now), FRESH["spot"])
    if not rows:
        return None
    t = np.array([int(r["open_time_ms"]) for r in rows], dtype=np.int64)
    return {"quote": RS.grid_values(t, np.array([float(r["quote_volume"]) for r in rows]), b.t0, b.n),
            "taker_buy_quote": RS.grid_values(t, np.array([float(r["taker_buy_quote"]) for r in rows]), b.t0, b.n),
            "close": RS.grid_values(t, np.array([float(r["close"]) for r in rows]), b.t0, b.n)}


async def _stress(conn, now: datetime, sources: dict) -> list:
    rows = await conn.fetch_feed_stress_hours(start=now - timedelta(hours=12), end=now)
    newest = max((int(r["hour_ms"]) + HOUR_MS for r in rows), default=None)
    sources["stress"] = _source(bool(rows), newest, to_ms(now), FRESH["stress"])
    return [dict(r) for r in rows]


async def _flow15(conn, cfg, now: datetime, sources: dict) -> Optional[dict]:
    fetch = getattr(conn, "fetch_live_flow_15m", None)
    if fetch is None:
        sources["flow15"] = _source(False, None, to_ms(now), None)
        return None
    now_ms = to_ms(now)
    end_ms = now_ms - now_ms % RS.GRID15_MS
    start_ms = end_ms - (RS.REF_STEPS_15 + 8) * RS.GRID15_MS
    rows = await fetch(exchange="binance", symbol=cfg.symbol, start=from_ms(start_ms), end=from_ms(end_ms))
    n = (end_ms - start_ms) // RS.GRID15_MS
    buy, total = np.full(n, np.nan), np.full(n, np.nan)
    newest = None
    for r in rows:
        i = (int(r["bucket_ms"]) - start_ms) // RS.GRID15_MS
        if 0 <= i < n and int(r["minutes"]) == 15 and int(r["taker_minutes"]) == 15:
            buy[i], total[i] = float(r["taker_buy_volume"]), float(r["volume"])
            newest = int(r["bucket_ms"]) + RS.GRID15_MS
    sources["flow15"] = _source(newest is not None, newest, now_ms, FRESH["flow15"])
    if newest is None:
        return None
    return {"bucket_ms": start_ms + np.arange(n, dtype=np.int64) * RS.GRID15_MS, "buy": buy, "total": total}


def _grid_daily(b: Bars) -> dict:
    """{day_ms: (n_returns, sum r^2, sum r)} for the UTC days fully inside the grid."""
    r = np.full(b.n, np.nan)
    with np.errstate(invalid="ignore", divide="ignore"):
        r[1:] = np.log(b.close[1:] / b.close[:-1])
    out = {}
    first_day = -(-b.t0 // DAY_MS) * DAY_MS
    d = first_day
    while d + DAY_MS <= b.end_ms:
        a = (d - b.t0) // BAR_MS
        seg = r[a:a + 288]
        if a >= 1 and seg.size == 288:
            ok = np.isfinite(seg)
            out[d] = (int(ok.sum()), float(np.sum(seg[ok] ** 2)), float(np.sum(seg[ok])))
        d += DAY_MS
    return out


async def _daily_rv(conn, b: Bars, now: datetime, sources: dict) -> Optional[list]:
    """[(decision day ms, rv or None)] oldest first: the D2 decision of day D uses day D-1's RV;
    December 31 decisions do not exist (D2 decision grid) and a zero 24h return is ineligible."""
    from .history_data import in_protected_window
    today = to_ms(now) - to_ms(now) % DAY_MS
    if _daily_cache["day"] != today:
        fetch = getattr(conn, "fetch_hist_daily_rv", None)
        rows = await fetch(start=from_ms(today - D2_DAYS * DAY_MS), end=from_ms(today)) if fetch else []
        _daily_cache.update(day=today, rows={int(r["day_ms"]): (int(r["n"]), float(r["sum_r2"]), float(r.get("sum_r") or 0.0))
                                             for r in rows})
    days = dict(_daily_cache["rows"] or {})
    days.update(_grid_daily(b))
    if not days:
        sources["bars_daily"] = _source(False, None, to_ms(now), None)
        return None
    out = []
    for d in sorted(days):
        dec = d + DAY_MS
        dt = from_ms(dec)
        if dec > today or (dt.month == 12 and dt.day == 31):
            continue
        n, s2, s1 = days[d]
        valid = n == 288 and s1 != 0.0 and not in_protected_window(d) and not in_protected_window(dec - BAR_MS)
        out.append((dec, math.sqrt(s2) if valid else None))
    sources["bars_daily"] = _source(bool(out), out[-1][0] if out else None, to_ms(now), None)
    return out


async def build_inputs(conn, cfg, *, now: datetime, b: Bars, block: Mapping[str, Any],
                       regime: Optional[Mapping[str, Any]] = None,
                       market: Optional[Mapping[str, Any]] = None) -> EvidenceInputs:
    sources: dict = {"bars": _source(True, b.end_ms, to_ms(now), None),
                     "calendar": _source(True, to_ms(now), to_ms(now), None),
                     "labels": _source(bool((market or {}).get("interpretation")), to_ms(now), to_ms(now), None),
                     "d7": _source(regime is not None, to_ms(now), to_ms(now), None)}
    oi, ls = await _metrics(conn, b, now, sources)
    return EvidenceInputs(
        now_ms=to_ms(now), bars=b, oi=oi, ls=ls, dvol_at=await _dvol(conn, now, sources),
        book=await _depth(conn, b, now, sources), spot=await _spot(conn, b, now, sources),
        stress=await _stress(conn, now, sources), flow15=await _flow15(conn, cfg, now, sources),
        daily_rv=await _daily_rv(conn, b, now, sources), regime=regime,
        levels=list(((block.get("levels") or {}).get("all")) or ()), events=list(block.get("events") or ()),
        weekend=bool(block.get("weekend")), labels=(market or {}).get("interpretation"), sources=sources)
