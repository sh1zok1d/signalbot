"""
REST backfill: 30 days of klines / open interest / funding / mark price per
exchange, per spec section 2. Liquidations and order flow are NEVER
backfilled - they only start accumulating live from process start
(config.yaml backfill.liquidations_orderflow_backfill: false).

Design notes / things flagged for your review rather than silently faked:

* Only Binance's public kline payload includes a taker-buy/sell split.
  Bybit/OKX/Bitget historical klines do not, so taker_buy_volume /
  taker_sell_volume are left NULL for their backfilled rows (not zero -
  "unknown" vs "zero" matters for taker_delta later). Live ingestion (stage 1
  data_ingestion/) computes the real split from tick trades for ALL 4
  exchanges going forward, so this NULL gap is backfill-only and shrinks
  every day the bot runs.
* Exchange historical open-interest / mark-price endpoints vary a lot in
  retention and granularity (Binance: 5m buckets, ~30d retention. Bybit:
  5m buckets. OKX/Bitget: coverage here is best-effort and may come back
  empty depending on what's exposed publicly right now). Any source that
  fails or returns nothing gets its backfill_runs row marked 'partial' or
  'failed' with a note - never silently zero-filled - per spec:
  "missing_history_handling: mark_run_as_partial".

VERIFY: exact REST paths/params reflect this model's training-data knowledge
of each exchange's API and were NOT tested against a live network (this
sandbox has no network access). Expect to need small fixes once you run this
against the real endpoints - treat it as a strong first draft, not gospel.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Callable, Optional

import aiohttp

from common.symbol_mapper import to_exchange_symbol
from storage.db import Database

logger = logging.getLogger(__name__)

REQUEST_DELAY_S = 0.15
MAX_RETRIES = 5

# Max simultaneous in-flight REST requests across ALL exchanges. Backfill now
# runs the 4 exchanges concurrently (asyncio.gather) to shrink the wall-clock
# window between backfill_end and live start; this semaphore bounds the total
# request rate so 4 parallel exchanges don't issue uncontrolled bursts. Each
# exchange additionally paces itself with REQUEST_DELAY_S between its own pages.
_CONCURRENCY = 4
_rate_sem: Optional["asyncio.Semaphore"] = None


class HttpClientError(RuntimeError):
    """A 4xx response we deliberately do NOT retry (client-side error, e.g.
    Binance OI -1130 'startTime is invalid'). Carries the full status + body so
    callers can log the exact error and decide how to react instead of blindly
    retrying five times and dying."""

    def __init__(self, status: int, body: str):
        self.status = status
        self.body = body
        super().__init__(f"HTTP {status}: {body[:300]}")


async def _get_json(session: aiohttp.ClientSession, url: str, params: dict) -> dict:
    if _rate_sem is not None:
        async with _rate_sem:
            return await _get_json_inner(session, url, params)
    return await _get_json_inner(session, url, params)


async def _get_json_inner(session: aiohttp.ClientSession, url: str, params: dict) -> dict:
    last_exc: Optional[Exception] = None
    for attempt in range(MAX_RETRIES):
        try:
            async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=20)) as resp:
                if resp.status == 429:
                    wait = 2 ** attempt
                    logger.warning("Rate limited (%s), backing off %ss", url, wait)
                    await asyncio.sleep(wait)
                    continue
                # 4xx are client errors (bad params, out-of-retention window):
                # retrying is pointless and hides the real cause. Surface the
                # full body once so the caller can log/handle it precisely.
                if 400 <= resp.status < 500:
                    body = await resp.text()
                    raise HttpClientError(resp.status, body)
                resp.raise_for_status()
                return await resp.json()
        except HttpClientError:
            raise
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            await asyncio.sleep(min(2 ** attempt, 10))
    raise RuntimeError(f"GET {url} failed after {MAX_RETRIES} retries: {last_exc}")


def _ms(dt: datetime) -> int:
    return int(dt.timestamp() * 1000)


def _from_ms(ms: int) -> datetime:
    return datetime.fromtimestamp(ms / 1000.0, tz=timezone.utc)


async def _run_source(db: Database, exchange: str, symbol: str, source: str,
                       window_start: datetime, window_end: datetime,
                       coro_factory: Callable[[], "asyncio.Future"]) -> None:
    if await db.has_complete_backfill(exchange, symbol, source, window_start):
        logger.info("[%s] %s backfill already complete for this window, skipping", exchange, source)
        return
    run_id = await db.start_backfill_run(exchange, symbol, source, window_start, window_end)
    try:
        rows_written, note, status = await coro_factory()
        await db.finish_backfill_run(run_id, status, rows_written, note)
        logger.info("[%s] %s backfill: %s rows, status=%s%s", exchange, source, rows_written,
                    status, f" ({note})" if note else "")
    except Exception as exc:  # noqa: BLE001
        logger.exception("[%s] %s backfill failed", exchange, source)
        await db.finish_backfill_run(run_id, "failed", 0, str(exc))


# ============================================================
# Reusable per-exchange 1m kline fetchers (module-level so both the 30d
# backfill closures below AND the post-backfill gap-fill use IDENTICAL paging
# logic — no risk of the two drifting). Each returns rows in insert_klines
# tuple shape: (exchange, symbol, ts, open, high, low, close, volume,
# taker_buy, taker_sell, trades_count). Half-open window [start_ms, end_ms).
# ============================================================
async def _klines_binance(session: aiohttp.ClientSession, symbol: str,
                          start_ms: int, end_ms: int) -> list[tuple]:
    base = "https://fapi.binance.com"
    rows: list[tuple] = []
    cursor = start_ms
    while cursor < end_ms:
        data = await _get_json(session, f"{base}/fapi/v1/klines", {
            "symbol": symbol, "interval": "1m", "startTime": cursor,
            "endTime": end_ms, "limit": 1500,
        })
        if not data:
            break
        for c in data:
            open_t, o, h, l, cl, vol, _ct, _qv, n, tbb, _tbq, _ig = c
            taker_buy = float(tbb)
            rows.append(("binance", symbol, _from_ms(open_t), float(o), float(h), float(l),
                         float(cl), float(vol), taker_buy, float(vol) - taker_buy, int(n)))
        cursor = data[-1][0] + 60_000
        await asyncio.sleep(REQUEST_DELAY_S)
    return rows


async def _klines_bybit(session: aiohttp.ClientSession, symbol: str,
                        start_ms: int, end_ms: int) -> list[tuple]:
    base = "https://api.bybit.com"
    rows: list[tuple] = []
    end_cursor = end_ms
    while end_cursor > start_ms:
        data = await _get_json(session, f"{base}/v5/market/kline", {
            "category": "linear", "symbol": symbol, "interval": "1",
            "end": end_cursor, "limit": 1000,
        })
        items = data.get("result", {}).get("list", [])
        if not items:
            break
        for it in items:  # newest-first: [start, o, h, l, c, vol, turnover]
            ts, o, h, l, cl, vol, _turn = it
            if int(ts) < start_ms:  # bound the backward page to the window
                continue
            rows.append(("bybit", symbol, _from_ms(int(ts)), float(o), float(h), float(l),
                         float(cl), float(vol), None, None, None))
        oldest_ts = int(items[-1][0])
        if oldest_ts <= start_ms:
            break
        end_cursor = oldest_ts - 1
        await asyncio.sleep(REQUEST_DELAY_S)
    return rows


async def _klines_okx(session: aiohttp.ClientSession, symbol: str,
                      start_ms: int, end_ms: int) -> list[tuple]:
    base = "https://www.okx.com"
    inst_id = to_exchange_symbol("okx", symbol, "perp")
    rows: list[tuple] = []
    after_cursor = end_ms
    while True:
        data = await _get_json(session, f"{base}/api/v5/market/history-candles", {
            "instId": inst_id, "bar": "1m", "after": after_cursor, "limit": 100,
        })
        items = data.get("data", [])
        if not items:
            break
        for c in items:  # newest-first: [ts, o, h, l, c, vol, ...]
            ts, o, h, l, cl, vol = c[0], c[1], c[2], c[3], c[4], c[5]
            if int(ts) < start_ms:
                continue
            rows.append(("okx", symbol, _from_ms(int(ts)), float(o), float(h), float(l),
                         float(cl), float(vol), None, None, None))
        oldest_ts = int(items[-1][0])
        if oldest_ts <= start_ms:
            break
        after_cursor = oldest_ts
        await asyncio.sleep(REQUEST_DELAY_S)
    return rows


async def _klines_bitget(session: aiohttp.ClientSession, symbol: str,
                         start_ms: int, end_ms: int) -> list[tuple]:
    base = "https://api.bitget.com"
    product_type = "USDT-FUTURES"
    rows: list[tuple] = []
    end_cursor = end_ms
    while end_cursor > start_ms:
        data = await _get_json(session, f"{base}/api/v2/mix/market/history-candles", {
            "symbol": symbol, "productType": product_type, "granularity": "1m",
            "endTime": end_cursor, "limit": 200,
        })
        items = data.get("data", [])
        if not items:
            break
        for c in items:  # ascending: [ts, o, h, l, c, baseVol, quoteVol]
            ts, o, h, l, cl, vol = c[0], c[1], c[2], c[3], c[4], c[5]
            if int(ts) < start_ms:
                continue
            rows.append(("bitget", symbol, _from_ms(int(ts)), float(o), float(h), float(l),
                         float(cl), float(vol), None, None, None))
        oldest_ts = int(items[0][0])  # ascending -> first is oldest
        if oldest_ts <= start_ms:
            break
        end_cursor = oldest_ts
        await asyncio.sleep(REQUEST_DELAY_S)
    return rows


KLINES_FETCHERS = {
    "binance": _klines_binance,
    "bybit": _klines_bybit,
    "okx": _klines_okx,
    "bitget": _klines_bitget,
}


# ============================================================
# BINANCE
# ============================================================
async def backfill_binance(session: aiohttp.ClientSession, db: Database, symbol: str,
                            window_start: datetime, window_end: datetime) -> None:
    base = "https://fapi.binance.com"

    async def klines():
        rows = await _klines_binance(session, symbol, _ms(window_start), _ms(window_end))
        written = await db.insert_klines(rows, source="backfill")
        return written, "", "complete"

    async def open_interest():
        # Binance's openInterestHist has a shorter retention than 30d: a
        # startTime older than ~29d23h returns 400 code -1130 ("startTime is
        # invalid"). We do NOT react to any -1130 by blindly shrinking the
        # window; instead we (1) probe a small recent range to confirm the
        # endpoint itself works, (2) clamp the start to a safe boundary rounded
        # to the 5m bucket, (3) paginate, (4) record in the note if we had to
        # shorten. Verified live: unaligned startTime is accepted, only depth
        # matters, so the boundary is a retention limit, not an alignment one.
        BUCKET_MS = 5 * 60_000
        end_ms = _ms(window_end)
        req_start = _ms(window_start)
        safe_earliest = end_ms - int((29 * 24 * 3600 + 23 * 3600) * 1000)  # now - 29d23h
        eff_start = max(req_start, safe_earliest)
        eff_start = (eff_start // BUCKET_MS) * BUCKET_MS  # align to 5m
        shortened = eff_start > req_start

        oi_url = f"{base}/futures/data/openInterestHist"

        # (1) Probe the most recent hour first. If this fails, it's not a
        # retention problem — log the full body and fail loudly.
        probe_start = ((end_ms - 3600_000) // BUCKET_MS) * BUCKET_MS
        try:
            await _get_json(session, oi_url, {
                "symbol": symbol, "period": "5m",
                "startTime": probe_start, "endTime": end_ms, "limit": 12,
            })
        except HttpClientError as exc:
            logger.error("[binance] OI probe failed (endpoint issue, not retention): "
                         "status=%s body=%s", exc.status, exc.body)
            return 0, f"OI probe failed HTTP {exc.status}: {exc.body[:120]}", "failed"

        # (2) Paginate from the clamped, aligned start.
        rows = []
        cursor = eff_start
        while cursor < end_ms:
            try:
                data = await _get_json(session, oi_url, {
                    "symbol": symbol, "period": "5m", "startTime": cursor,
                    "endTime": min(cursor + 500 * BUCKET_MS, end_ms), "limit": 500,
                })
            except HttpClientError as exc:
                logger.error("[binance] OI page failed at cursor=%s: status=%s body=%s",
                             cursor, exc.status, exc.body)
                break
            if not data:
                cursor += 500 * BUCKET_MS
                await asyncio.sleep(REQUEST_DELAY_S)
                continue
            for item in data:
                # sumOpenInterest = base (BTC), sumOpenInterestValue = USD (both
                # provided directly by Binance — no coefficient assumed).
                rows.append(("binance", symbol, _from_ms(item["timestamp"]),
                             float(item["sumOpenInterest"]), "base", None, "BTC",
                             float(item["sumOpenInterestValue"])))
            cursor = data[-1]["timestamp"] + BUCKET_MS
            await asyncio.sleep(REQUEST_DELAY_S)

        written = await db.insert_open_interest(rows, source="backfill")
        note = ""
        if shortened:
            note = (f"OI window shortened to {_from_ms(eff_start):%Y-%m-%d %H:%MZ} "
                    f"(endpoint rejects startTime older than ~29d23h)")
        elif not written:
            note = "endpoint returned no data"
        # Complete when we got data covering the (possibly clamped) window;
        # partial when clamped or empty so it stays visible in backfill_runs.
        status = "complete" if written and not shortened else "partial"
        return written, note, status

    async def funding():
        rows = []
        cursor = _ms(window_start)
        end_ms = _ms(window_end)
        while cursor < end_ms:
            data = await _get_json(session, f"{base}/fapi/v1/fundingRate", {
                "symbol": symbol, "startTime": cursor, "endTime": end_ms, "limit": 1000,
            })
            if not data:
                break
            for item in data:
                rows.append(("binance", symbol, _from_ms(item["fundingTime"]),
                             float(item["fundingRate"]), None))
            cursor = data[-1]["fundingTime"] + 1
            await asyncio.sleep(REQUEST_DELAY_S)
        written = await db.insert_funding(rows, source="backfill")
        return written, "", "complete"

    async def mark_price():
        rows = []
        cursor = _ms(window_start)
        end_ms = _ms(window_end)
        while cursor < end_ms:
            data = await _get_json(session, f"{base}/fapi/v1/markPriceKlines", {
                "symbol": symbol, "interval": "1m", "startTime": cursor,
                "endTime": end_ms, "limit": 1500,
            })
            if not data:
                break
            for c in data:
                open_t, _o, _h, _l, cl = c[0], c[1], c[2], c[3], c[4]
                rows.append(("binance", symbol, _from_ms(open_t), float(cl)))
            cursor = data[-1][0] + 60_000
            await asyncio.sleep(REQUEST_DELAY_S)
        written = await db.insert_mark_price(rows, source="backfill")
        return written, "", "complete"

    await _run_source(db, "binance", symbol, "klines", window_start, window_end, klines)
    await _run_source(db, "binance", symbol, "open_interest", window_start, window_end, open_interest)
    await _run_source(db, "binance", symbol, "funding", window_start, window_end, funding)
    await _run_source(db, "binance", symbol, "mark_price", window_start, window_end, mark_price)


# ============================================================
# BYBIT
# ============================================================
async def backfill_bybit(session: aiohttp.ClientSession, db: Database, symbol: str,
                          window_start: datetime, window_end: datetime) -> None:
    base = "https://api.bybit.com"

    async def klines():
        rows = await _klines_bybit(session, symbol, _ms(window_start), _ms(window_end))
        written = await db.insert_klines(rows, source="backfill")
        return written, "", "complete"

    async def open_interest():
        rows = []
        end_cursor = _ms(window_end)
        start_ms = _ms(window_start)
        while end_cursor > start_ms:
            data = await _get_json(session, f"{base}/v5/market/open-interest", {
                "category": "linear", "symbol": symbol, "intervalTime": "5min",
                "endTime": end_cursor, "limit": 200,
            })
            items = data.get("result", {}).get("list", [])
            if not items:
                break
            for item in items:
                # Bybit historical OI is base (BTC); no USD in this endpoint.
                rows.append(("bybit", symbol, _from_ms(int(item["timestamp"])),
                             float(item["openInterest"]), "base", None, "BTC", None))
            oldest_ts = int(items[-1]["timestamp"])
            if oldest_ts <= start_ms:
                break
            end_cursor = oldest_ts - 1
            await asyncio.sleep(REQUEST_DELAY_S)
        written = await db.insert_open_interest(rows, source="backfill")
        note = "" if written else "endpoint returned no data (retention window may be shorter than 30d)"
        return written, note, "complete" if written else "partial"

    async def funding():
        rows = []
        end_cursor = _ms(window_end)
        start_ms = _ms(window_start)
        while end_cursor > start_ms:
            data = await _get_json(session, f"{base}/v5/market/funding/history", {
                "category": "linear", "symbol": symbol, "endTime": end_cursor, "limit": 200,
            })
            items = data.get("result", {}).get("list", [])
            if not items:
                break
            for item in items:
                rows.append(("bybit", symbol, _from_ms(int(item["fundingRateTimestamp"])),
                             float(item["fundingRate"]), None))
            oldest_ts = int(items[-1]["fundingRateTimestamp"])
            if oldest_ts <= start_ms:
                break
            end_cursor = oldest_ts - 1
            await asyncio.sleep(REQUEST_DELAY_S)
        written = await db.insert_funding(rows, source="backfill")
        return written, "", "complete"

    async def mark_price():
        # Bybit mark-price history lives on a DEDICATED endpoint,
        # /v5/market/mark-price-kline, NOT /v5/market/kline?category=mark
        # ("mark" is not a valid category and returns retCode 10001). Rows are
        # [start, open, high, low, close], newest-first, so we page backward by
        # the `end` cursor. Verified live.
        rows = []
        end_cursor = _ms(window_end)
        start_ms = _ms(window_start)
        while end_cursor > start_ms:
            data = await _get_json(session, f"{base}/v5/market/mark-price-kline", {
                "category": "linear", "symbol": symbol, "interval": "1",
                "end": end_cursor, "limit": 1000,
            })
            items = data.get("result", {}).get("list", [])
            if not items:
                break
            for item in items:
                ts, _o, _h, _l, cl = item[0], item[1], item[2], item[3], item[4]
                rows.append(("bybit", symbol, _from_ms(int(ts)), float(cl)))
            oldest_ts = int(items[-1][0])
            if oldest_ts <= start_ms:
                break
            end_cursor = oldest_ts - 1
            await asyncio.sleep(REQUEST_DELAY_S)
        written = await db.insert_mark_price(rows, source="backfill")
        return written, "", "complete" if written else "partial"

    await _run_source(db, "bybit", symbol, "klines", window_start, window_end, klines)
    await _run_source(db, "bybit", symbol, "open_interest", window_start, window_end, open_interest)
    await _run_source(db, "bybit", symbol, "funding", window_start, window_end, funding)
    await _run_source(db, "bybit", symbol, "mark_price", window_start, window_end, mark_price)


# ============================================================
# OKX  (USDT-perpetual swap; instId via common.symbol_mapper)
# ============================================================
async def backfill_okx(session: aiohttp.ClientSession, db: Database, symbol: str,
                        window_start: datetime, window_end: datetime) -> None:
    base = "https://www.okx.com"
    # Canonical symbol stays in every stored row; inst_id is only the OKX API id.
    inst_id = to_exchange_symbol("okx", symbol, "perp")

    async def klines():
        rows = await _klines_okx(session, symbol, _ms(window_start), _ms(window_end))
        written = await db.insert_klines(rows, source="backfill")
        return written, "many small pages (100/req) - slow but complete", "complete"

    async def funding():
        rows = []
        after_cursor = _ms(window_end)
        start_ms = _ms(window_start)
        while True:
            data = await _get_json(session, f"{base}/api/v5/public/funding-rate-history", {
                "instId": inst_id, "after": after_cursor, "limit": 100,
            })
            items = data.get("data", [])
            if not items:
                break
            for item in items:
                rows.append(("okx", symbol, _from_ms(int(item["fundingTime"])),
                             float(item["fundingRate"]), None))
            oldest_ts = int(items[-1]["fundingTime"])
            if oldest_ts <= start_ms:
                break
            after_cursor = oldest_ts
            await asyncio.sleep(REQUEST_DELAY_S)
        written = await db.insert_funding(rows, source="backfill")
        return written, "", "complete"

    async def mark_price():
        rows = []
        after_cursor = _ms(window_end)
        start_ms = _ms(window_start)
        while True:
            data = await _get_json(session, f"{base}/api/v5/market/history-mark-price-candles", {
                "instId": inst_id, "bar": "1m", "after": after_cursor, "limit": 100,
            })
            items = data.get("data", [])
            if not items:
                break
            for c in items:
                ts, _o, _h, _l, cl = c[0], c[1], c[2], c[3], c[4]
                if int(ts) < start_ms:
                    continue
                rows.append(("okx", symbol, _from_ms(int(ts)), float(cl)))
            oldest_ts = int(items[-1][0])
            if oldest_ts <= start_ms:
                break
            after_cursor = oldest_ts
            await asyncio.sleep(REQUEST_DELAY_S)
        written = await db.insert_mark_price(rows, source="backfill")
        return written, "", "complete" if written else "partial"

    async def open_interest():
        # No confirmed reliable historical per-instrument OI endpoint for OKX
        # at 1m/5m granularity going back 30 days as of this writing - do not
        # fabricate. Mark partial explicitly so it's visible in backfill_runs
        # rather than silently missing.
        return 0, "no verified historical OI endpoint available; live-only from process start", "partial"

    await _run_source(db, "okx", symbol, "klines", window_start, window_end, klines)
    await _run_source(db, "okx", symbol, "open_interest", window_start, window_end, open_interest)
    await _run_source(db, "okx", symbol, "funding", window_start, window_end, funding)
    await _run_source(db, "okx", symbol, "mark_price", window_start, window_end, mark_price)


# ============================================================
# BITGET
# ============================================================
async def backfill_bitget(session: aiohttp.ClientSession, db: Database, symbol: str,
                           window_start: datetime, window_end: datetime) -> None:
    base = "https://api.bitget.com"
    product_type = "USDT-FUTURES"

    async def klines():
        # Uses the dedicated /history-candles endpoint (see _klines_bitget):
        # the regular /candles endpoint ignores startTime over a wide range and
        # returned only the most recent ~1000 bars (the original bug). Here we
        # additionally verify the actual stored range vs the 30d window.
        start_ms = _ms(window_start)
        rows = await _klines_bitget(session, symbol, start_ms, _ms(window_end))
        written = await db.insert_klines(rows, source="backfill")
        note = ""
        status = "complete"
        if rows:
            actual_oldest = min(r[2] for r in rows)
            short_by_h = (actual_oldest - _from_ms(start_ms)).total_seconds() / 3600.0
            if short_by_h > 6:
                note = (f"history starts {actual_oldest:%Y-%m-%d %H:%MZ}, "
                        f"~{short_by_h:.0f}h short of 30d window")
                status = "partial"
        else:
            note = "history-candles returned no data"
            status = "partial"
        return written, note, status

    async def funding():
        rows = []
        page = 1
        start_ms = _ms(window_start)
        stop = False
        while not stop:
            data = await _get_json(session, f"{base}/api/v2/mix/market/history-fund-rate", {
                "symbol": symbol, "productType": product_type, "pageSize": 100, "pageNo": page,
            })
            items = data.get("data", [])
            if not items:
                break
            for item in items:
                ts = int(item["fundingTime"])
                if ts < start_ms:
                    stop = True
                    continue
                rows.append(("bitget", symbol, _from_ms(ts), float(item["fundingRate"]), None))
            page += 1
            await asyncio.sleep(REQUEST_DELAY_S)
        written = await db.insert_funding(rows, source="backfill")
        return written, "", "complete" if written else "partial"

    async def open_interest():
        return 0, "no verified historical OI endpoint available; live-only from process start", "partial"

    async def mark_price():
        return 0, "no verified historical mark-price endpoint available; live-only from process start", "partial"

    await _run_source(db, "bitget", symbol, "klines", window_start, window_end, klines)
    await _run_source(db, "bitget", symbol, "open_interest", window_start, window_end, open_interest)
    await _run_source(db, "bitget", symbol, "funding", window_start, window_end, funding)
    await _run_source(db, "bitget", symbol, "mark_price", window_start, window_end, mark_price)


BACKFILL_FUNCS = {
    "binance": backfill_binance,
    "bybit": backfill_bybit,
    "okx": backfill_okx,
    "bitget": backfill_bitget,
}


async def run_backfill(db: Database, symbol: str, exchanges: list[str], window_days: int) -> None:
    global _rate_sem
    window_end = datetime.now(tz=timezone.utc)
    window_start = window_end - timedelta(days=window_days)
    # Run the exchanges concurrently to keep the wall-clock backfill window
    # short (the old serial loop took ~11min, opening an 11min backfill->live
    # gap). A shared semaphore caps the TOTAL in-flight request rate.
    _rate_sem = asyncio.Semaphore(_CONCURRENCY)

    async def _one(exchange: str) -> None:
        func = BACKFILL_FUNCS.get(exchange)
        if func is None:
            logger.warning("No backfill implementation for %s, skipping", exchange)
            return
        logger.info("Starting backfill for %s (%s -> %s)", exchange, window_start, window_end)
        await func(session, db, symbol, window_start, window_end)

    try:
        async with aiohttp.ClientSession() as session:
            await asyncio.gather(*(_one(ex) for ex in exchanges))
    finally:
        _rate_sem = None
    logger.info("Backfill pass complete for all configured exchanges")


async def run_gap_fill(db: Database, symbol: str, exchanges: list[str]) -> None:
    """Fill the klines gap between the newest bar already in the DB and the
    current CLOSED minute, per exchange, right before live ingestion starts.

    Parallelising backfill (above) shrinks but does not eliminate the gap:
    time still passes between backfill_end and the first live WS bar. This
    closes that remaining gap by REST so live starts on a continuous series.
    Idempotent (upsert); safe to run even if already current. Note: for an
    exchange whose live WS trade tape is blocked (e.g. Binance from an EEA IP),
    REST klines still work, so this keeps its history current at startup even
    though live bars won't accumulate.
    """
    global _rate_sem
    now = datetime.now(tz=timezone.utc)
    # Last fully-closed minute (exclusive upper bound for the half-open window).
    closed_minute = now.replace(second=0, microsecond=0)
    end_ms = _ms(closed_minute)  # bars with ts < end_ms, i.e. up to closed_minute-1m
    _rate_sem = asyncio.Semaphore(_CONCURRENCY)

    async def _one(session: aiohttp.ClientSession, exchange: str) -> None:
        fetch = KLINES_FETCHERS.get(exchange)
        if fetch is None:
            return
        last = await db.fetchval(
            "SELECT max(ts) FROM klines_1m WHERE exchange=$1 AND symbol=$2", exchange, symbol)
        if last is None:
            logger.warning("[%s] gap-fill: no bars in DB yet, skipping (run backfill first)", exchange)
            return
        start_ms = _ms(last) + 60_000
        if start_ms >= end_ms:
            logger.info("[%s] gap-fill: already current (last bar %s)", exchange, last)
            return
        try:
            rows = await fetch(session, symbol, start_ms, end_ms)
        except Exception as exc:  # noqa: BLE001
            logger.warning("[%s] gap-fill failed: %s", exchange, exc)
            return
        written = await db.insert_klines(rows, source="backfill")
        logger.info("[%s] gap-fill %s -> %s: %s bars", exchange, last, closed_minute, written)

    try:
        async with aiohttp.ClientSession() as session:
            await asyncio.gather(*(_one(session, ex) for ex in exchanges))
    finally:
        _rate_sem = None
    logger.info("Gap-fill pass complete")
