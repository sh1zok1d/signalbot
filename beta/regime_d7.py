"""Live D7 hour state for the /btc regime line.

The hour aggregation and the impact state are the same arithmetic as
`aggregate_completed_hours` and `build_d7_states` in
`scripts/research/discovery_sprint_02_impl.py`: 60 one-minute bars, log return,
relative quote volume, and a strict linear p90. This module does not import
that research code and does not stop at the research protected-start cutoff.
Incomplete hours are skipped and never zero-filled.

The tables are display inputs. Nothing here counts whether the next hour was
also in the state.
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Awaitable, Callable, Mapping, Optional, Sequence

import numpy as np

from common.versioning import canonical_json

logger = logging.getLogger("beta.regime_d7")

BAR_MS = 60_000
HOUR_MS = 3_600_000
BARS_PER_HOUR = 60
TRAILING_WINDOW = 720
D7_PCTL = 90.0
PERCENTILE_METHOD = "linear"
# Prior valid hours required before a state boolean exists (research index 1440).
WARMUP_VALID_HOURS = 1440
FAPI_URL = "https://fapi.binance.com/fapi/v1/klines"
FAPI_LIMIT = 1500
MIN_ONCE_BARS = 120
DEFAULT_BACKFILL_DAYS = 90
DEFAULT_PACE_S = 0.2
HOUR_STATE_STALE_AFTER = timedelta(minutes=70)
COMPUTE_GRACE = timedelta(minutes=10)

DEFINITION_PAYLOAD = {
    "name": "D7_HIGH_IMPACT_V1",
    "instrument": "BINANCE_USD_M_BTCUSDT",
    "symbol": "BTCUSDT",
    "interval": "1m",
    "hour": "UTC clock hour, all 60 1m bars required",
    "ret": "ln(close of the last 1m bar / open of the first 1m bar)",
    "quote_volume_1h": "sum of 1m quote asset volume",
    "incomplete_hours": "skipped, never zero-filled",
    "qrel": "quote_volume_1h / median(previous 720 valid hourly quote volumes)",
    "impact": "abs(ret) / qrel",
    "state": "impact > p90 of the previous 720 valid impacts",
    "percentile_method": PERCENTILE_METHOD,
    "trailing_window": TRAILING_WINDOW,
    "pctl": D7_PCTL,
    "warmup_prior_valid_hours": WARMUP_VALID_HOURS,
}


def definition_digest() -> str:
    return hashlib.sha256(canonical_json(DEFINITION_PAYLOAD).encode("utf-8")).hexdigest()


def percentile(values: Sequence[float], p: float) -> float:
    arr = np.asarray(list(values), dtype=np.float64)
    if arr.size == 0:
        raise ValueError("EMPTY_PERCENTILE")
    return float(np.percentile(arr, p, method=PERCENTILE_METHOD))


def median(values: Sequence[float]) -> float:
    arr = np.asarray(list(values), dtype=np.float64)
    if arr.size == 0:
        raise ValueError("EMPTY_MEDIAN")
    return float(np.median(arr))


@dataclass(frozen=True)
class MinuteBar:
    open_time_ms: int
    available_at_ms: int
    open: float
    close: float
    quote_volume: float


@dataclass(frozen=True)
class HourBar:
    hour_start_ms: int
    available_at_ms: int
    open_1h: float
    close_1h: float
    quote_volume_1h: float
    ret_abs_1h: float
    event_return: float


@dataclass
class D7HourState:
    hour: HourBar
    qrel_1h: Optional[float]
    impact_proxy: Optional[float]
    p90: Optional[float]
    d7_state: Optional[bool]


def aggregate_completed_hours(bars: Sequence[MinuteBar]) -> list[HourBar]:
    """UTC clock hours that contain all 60 one-minute bars. No protected-year wall."""
    by_open = {int(bar.open_time_ms): bar for bar in bars}
    if not by_open:
        return []
    hours: list[HourBar] = []
    first = min(by_open)
    last_open = max(by_open)
    hour_start = first - (first % HOUR_MS)
    while hour_start <= last_open:
        members: list[MinuteBar] = []
        complete = True
        for k in range(BARS_PER_HOUR):
            bar = by_open.get(hour_start + k * BAR_MS)
            if bar is None:
                complete = False
                break
            members.append(bar)
        if complete:
            first_bar = members[0]
            last_bar = members[-1]
            if last_bar.available_at_ms != hour_start + HOUR_MS:
                raise ValueError(f"HOUR_AVAILABLE_AT:{hour_start}:{last_bar.available_at_ms}")
            if first_bar.open <= 0.0 or last_bar.close <= 0.0:
                hour_start += HOUR_MS
                continue
            event_return = math.log(last_bar.close / first_bar.open)
            if not math.isfinite(event_return):
                hour_start += HOUR_MS
                continue
            hours.append(HourBar(
                hour_start_ms=hour_start,
                available_at_ms=hour_start + HOUR_MS,
                open_1h=first_bar.open,
                close_1h=last_bar.close,
                quote_volume_1h=sum(bar.quote_volume for bar in members),
                ret_abs_1h=abs(event_return),
                event_return=event_return,
            ))
        hour_start += HOUR_MS
    return hours


def build_d7_states(hours: Sequence[HourBar]) -> list[D7HourState]:
    """Causal impact state. Windows use only hours already completed."""
    states: list[D7HourState] = []
    valid_volumes: list[float] = []
    valid_impacts: list[float] = []
    for hour in hours:
        qrel = None
        impact = None
        p90 = None
        state = None
        vol_ok = math.isfinite(hour.quote_volume_1h)
        rv_ok = math.isfinite(hour.ret_abs_1h)
        if vol_ok and len(valid_volumes) >= TRAILING_WINDOW:
            med = median(valid_volumes[-TRAILING_WINDOW:])
            if math.isfinite(med) and med > 0.0 and hour.quote_volume_1h > 0.0:
                qrel = hour.quote_volume_1h / med
                if math.isfinite(qrel) and qrel > 0.0 and rv_ok:
                    impact = hour.ret_abs_1h / qrel
                    if not math.isfinite(impact):
                        impact = None
                else:
                    qrel = None
        if impact is not None and len(valid_impacts) >= TRAILING_WINDOW:
            p90 = percentile(valid_impacts[-TRAILING_WINDOW:], D7_PCTL)
            state = bool(impact > p90)
        states.append(D7HourState(
            hour=hour, qrel_1h=qrel, impact_proxy=impact, p90=p90, d7_state=state))
        if vol_ok:
            valid_volumes.append(hour.quote_volume_1h)
        if impact is not None:
            valid_impacts.append(impact)
    return states


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _as_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        raise ValueError("D7 timestamps must be timezone-aware")
    return dt.astimezone(timezone.utc)


def last_completed_hour(now: datetime) -> datetime:
    """Clock hour H whose following hour is the one `now` sits in."""
    now = _as_utc(now)
    hour = now.replace(minute=0, second=0, microsecond=0)
    return hour - timedelta(hours=1)


def regime_payload(*, enabled: bool, now: datetime, row: Optional[Mapping],
                   valid_before: int, product_status: str) -> dict:
    """View-payload regime block. `shown` is decided here and stored with the view."""
    start = last_completed_hour(now)
    end = start + timedelta(hours=1)
    state = None
    available = None
    complete = False
    computed_at = None
    digest = definition_digest()
    if row is not None:
        row_start = row.get("hour_start")
        if isinstance(row_start, datetime) and _as_utc(row_start) == start:
            state = row.get("state")
            available = row.get("available_at")
            complete = bool(row.get("complete"))
            computed_at = row.get("computed_at")
            digest = row.get("definition_digest") or digest
    warmup = int(valid_before) >= WARMUP_VALID_HOURS
    market_ok = product_status not in ("DATA STALE", "DATA DEGRADED")
    on_time = isinstance(computed_at, datetime) and _as_utc(computed_at) < end + COMPUTE_GRACE
    shown = bool(enabled and market_ok and complete and state is True and warmup and on_time)
    return {
        "hour_start": _iso(start),
        "hour_end": _iso(end),
        "state": state if isinstance(state, bool) else None,
        "available_at": _iso(available) if isinstance(available, datetime) else None,
        "definition_digest": digest,
        "complete": complete,
        "warmup_complete": bool(enabled and warmup),
        "shown": shown,
    }


async def regime_for_status(conn, *, now: datetime, product_status: str) -> dict:
    start = last_completed_hour(now)
    row = await conn.fetch_d7_hour_state(start)
    valid_before = await conn.count_d7_valid_hours_before(start)
    return regime_payload(enabled=True, now=now, row=row, valid_before=valid_before,
                          product_status=product_status)


async def warmup_for_readiness(conn, *, now: datetime) -> dict:
    start = last_completed_hour(now)
    valid_before = await conn.count_d7_valid_hours_before(start)
    return {"warmup_complete": valid_before >= WARMUP_VALID_HOURS,
            "valid_hours_before": valid_before}


def _num(value) -> float:
    return float(Decimal(str(value)))


def parse_closed_kline(row, *, now_ms: int, fetched_at: datetime) -> Optional[dict]:
    """One Binance USD-M kline row, or None when the bar is still open."""
    if not isinstance(row, (list, tuple)) or len(row) < 8:
        raise ValueError("D7_KLINE_SHAPE")
    close_ms = int(row[6])
    if close_ms >= now_ms:
        return None
    open_ms = int(row[0])
    return {
        "open_time": datetime.fromtimestamp(open_ms / 1000.0, tz=timezone.utc),
        "open": _num(row[1]),
        "high": _num(row[2]),
        "low": _num(row[3]),
        "close": _num(row[4]),
        "quote_asset_volume": _num(row[7]),
        "close_time": datetime.fromtimestamp(close_ms / 1000.0, tz=timezone.utc),
        "fetched_at": fetched_at,
    }


def _ms(dt: datetime) -> int:
    return int(round(_as_utc(dt).timestamp() * 1000))


def _align_minute(ms: int) -> int:
    return ms - (ms % BAR_MS)


async def _default_fetcher(session, start_ms: int, limit: int):
    params = {"symbol": "BTCUSDT", "interval": "1m", "limit": int(limit), "startTime": int(start_ms)}
    async with session.get(FAPI_URL, params=params) as resp:
        resp.raise_for_status()
        body = await resp.json()
    if not isinstance(body, list):
        raise RuntimeError("D7_KLINE_SHAPE")
    return body


async def _pull_pages(fetcher, *, start_ms: int, now: datetime, pace_s: float,
                      pause: Callable[[float], Awaitable[None]], sink) -> dict:
    now_ms = _ms(now)
    cursor = start_ms
    requests = 0
    closed = 0
    while cursor < now_ms:
        rows = await fetcher(cursor, FAPI_LIMIT)
        requests += 1
        if not isinstance(rows, list):
            raise RuntimeError("D7_KLINE_SHAPE")
        if not rows:
            break
        page = []
        for row in rows:
            parsed = parse_closed_kline(row, now_ms=now_ms, fetched_at=now)
            if parsed is not None:
                page.append(parsed)
        if page:
            await sink(page)
            closed += len(page)
        last_open = int(rows[-1][0])
        next_cursor = last_open + BAR_MS
        if next_cursor <= cursor or len(rows) < FAPI_LIMIT or int(rows[-1][6]) >= now_ms:
            break
        cursor = next_cursor
        if pace_s:
            await pause(pace_s)
    return {"requests": requests, "closed_bars": closed}


async def _start_ms(conn, *, now: datetime, backfill_days: Optional[int]) -> int:
    now_ms = _ms(now)
    lo, hi = await conn.d7_kline_bounds()
    if backfill_days is None:
        floor = _align_minute(now_ms - MIN_ONCE_BARS * BAR_MS)
        if hi is None:
            return floor
        return min(_ms(hi), floor)
    target = _align_minute(now_ms - int(backfill_days) * 24 * HOUR_MS)
    if lo is None or _ms(lo) > target:
        return target
    return _ms(hi)


async def compute_missing_hour_states(conn, *, now: datetime) -> int:
    rows = await conn.fetch_d7_klines()
    bars = [MinuteBar(
        open_time_ms=_ms(r["open_time"]),
        available_at_ms=_ms(r["open_time"]) + BAR_MS,
        open=float(r["open"]),
        close=float(r["close"]),
        quote_volume=float(r["quote_asset_volume"]),
    ) for r in rows]
    digest = definition_digest()
    inserted = 0
    for state in build_d7_states(aggregate_completed_hours(bars)):
        hour = datetime.fromtimestamp(state.hour.hour_start_ms / 1000.0, tz=timezone.utc)
        wrote = await conn.insert_d7_hour_if_absent(
            hour_start=hour,
            complete=True,
            ret=state.hour.event_return,
            quote_volume_1h=state.hour.quote_volume_1h,
            qrel=state.qrel_1h,
            impact=state.impact_proxy,
            p90=state.p90,
            state=state.d7_state,
            available_at=hour + timedelta(hours=1),
            computed_at=now,
            definition_digest=digest,
        )
        inserted += int(wrote)
    return inserted


async def run_d7_job(store, *, now: datetime, mode: str, days: int = DEFAULT_BACKFILL_DAYS,
                     fetcher=None, pace_s: float = DEFAULT_PACE_S,
                     pause: Optional[Callable[[float], Awaitable[None]]] = None) -> dict:
    """Fetch closed 1m bars, then insert hour states that do not exist yet.

    `mode` is `once` (at least the last 120 bars, catch-up from the last stored
    bar) or `backfill` (from `days` ago, resuming when bars are already stored).
    """
    from storage.beta_v0_store import D7_LOCK_KEY

    if mode not in ("once", "backfill"):
        raise ValueError(f"unknown d7 mode {mode!r}")
    pause = pause or asyncio.sleep
    backfill_days = None if mode == "once" else int(days)
    async with store.advisory_lock(D7_LOCK_KEY) as acquired:
        if not acquired:
            return {"status": "BUSY", "mode": mode}
        own_session = fetcher is None
        session = None
        if own_session:
            import aiohttp
            session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30))
            fetcher = lambda start_ms, limit: _default_fetcher(session, start_ms, limit)  # noqa: E731
        try:
            async with store.connect() as conn:
                start_ms = await _start_ms(conn, now=now, backfill_days=backfill_days)

            async def sink(page):
                async with store.connect() as conn:
                    async with conn.transaction():
                        await conn.upsert_d7_klines(page)

            pulled = await _pull_pages(fetcher, start_ms=start_ms, now=now, pace_s=pace_s,
                                       pause=pause, sink=sink)
            async with store.connect() as conn:
                async with conn.transaction():
                    inserted = await compute_missing_hour_states(conn, now=now)
                    newest = await conn.newest_d7_available_at()
                    await conn.record_health("d7", now=now, success=True, detail={
                        "mode": mode, "closed_bars": pulled["closed_bars"],
                        "hours_inserted": inserted})
            return {"status": "OK", "mode": mode, "start_ms": start_ms,
                    "requests": pulled["requests"], "closed_bars": pulled["closed_bars"],
                    "hours_inserted": inserted,
                    "newest_available_at": newest}
        except Exception as exc:
            logger.warning("d7 kline job failed: %s", type(exc).__name__)
            try:
                async with store.connect() as conn:
                    await conn.record_health("d7", now=now, success=False, error_type=type(exc).__name__)
            except Exception as record_exc:  # noqa: BLE001 - the original fetch error is the one to raise
                logger.warning("d7 health record failed: %s", type(record_exc).__name__)
            raise
        finally:
            if session is not None:
                await session.close()
