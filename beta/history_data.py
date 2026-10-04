"""Binance USD-M BTCUSDT history from the official archive (PRODUCT_DECISION_V2 §2, §4).

Source: https://data.binance.vision (immutable daily / monthly objects with SHA-256 checksum
files). Two series:

- 5m klines from 2020-01 (monthly objects; daily objects for the current month and for a
  just-ended month whose monthly object is not published yet);
- the `metrics` series (5m open interest, base BTC and USD, and the global long/short account
  ratio) from 2020-09-01 (daily objects).

The owner opened 2025/2026 for product use (PRODUCT_DECISION_V2 §4); this module reads every
year up to yesterday (UTC), except the protected windows below (the E1-RUN-001 final holdout).
Protection is at the object level, before any request: an archive object whose period
intersects a protected window is never requested (a complete month that does is replaced by
its days that do not; a day that does is dropped whole, even when part of it lies outside),
and every request URL is checked again just before it is made. Rows inside a window are also
dropped after parsing, as a last line. Every object is checksum-verified before its rows are written, and
the object ledger (`beta_hist_objects`) makes the sync resumable and idempotent: an object
already OK is never fetched again. A missing object (404) leaves its bars absent; nothing is
filled in.

`sync_history` is the only function that does network I/O. Parsing is pure.
"""
from __future__ import annotations

import asyncio
import csv
import hashlib
import io
import logging
import re
import zipfile
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Awaitable, Callable, Iterable, Optional

logger = logging.getLogger("beta.history_data")

VISION_ROOT = "https://data.binance.vision/data/futures/um"
SYMBOL = "BTCUSDT"
KLINES_START = date(2020, 1, 1)
METRICS_START = date(2020, 9, 1)
MISSING_RETRY_DAYS = 14          # a 404 for an object younger than this is retried on every run
MISSING_MAX_ATTEMPTS = 3         # an older object that answered 404 this many times is left alone
DEFAULT_CONCURRENCY = 6
HISTORY_DATA_VERSION = "BETA_HISTORY_VISION_V1"

# AGENTS.md: the E1-RUN-001 final holdout is opened only by its frozen one-shot evaluator.
# The product history never requests an archive object that overlaps it, and never stores a bar
# or an OI snapshot inside it (PRODUCT_DECISION_V2 §4). Half-open: [start, end).
PROTECTED_WINDOWS = (
    ("E1-RUN-001 final holdout", datetime(2026, 8, 16, tzinfo=timezone.utc),
     datetime(2026, 8, 25, 17, 20, tzinfo=timezone.utc)),
)


def _protected_ms() -> list:
    return [(n, int(a.timestamp() * 1000), int(z.timestamp() * 1000)) for n, a, z in PROTECTED_WINDOWS]


def in_protected_window(ms: int) -> bool:
    """A timestamp (a bar's open, an OI snapshot's time) inside a protected window."""
    return any(a <= int(ms) < z for _n, a, z in _protected_ms())


def protected_overlap(start_ms: int, end_ms: int) -> Optional[str]:
    """The name of a protected window that the period [start_ms, end_ms) intersects, else None."""
    for name, a, z in _protected_ms():
        if int(start_ms) < z and a < int(end_ms):
            return name
    return None


def drop_protected(rows: list, key: str) -> list:
    return [r for r in rows if not in_protected_window(r[key])]


class ProtectedObjectRefused(RuntimeError):
    """A request for an archive object that overlaps a protected window (or whose period cannot
    be read from its name) was refused before it was made."""


_KEY_PERIOD = re.compile(r"-(\d{4})-(\d{2})(?:-(\d{2}))?\.zip(?:\.CHECKSUM)?$")


def key_period_ms(key_or_url: str) -> Optional[tuple]:
    """[start, end) in ms of the calendar period an archive object's name covers: a day
    (``…-YYYY-MM-DD.zip``) or a month (``…-YYYY-MM.zip``); None when the name has no period."""
    m = _KEY_PERIOD.search(key_or_url)
    if not m:
        return None
    y, mo, d = int(m.group(1)), int(m.group(2)), m.group(3)
    if d is not None:
        a = datetime(y, mo, int(d), tzinfo=timezone.utc)
        z = a + timedelta(days=1)
    else:
        a = datetime(y, mo, 1, tzinfo=timezone.utc)
        z = datetime(y + (mo == 12), mo % 12 + 1, 1, tzinfo=timezone.utc)
    return int(a.timestamp() * 1000), int(z.timestamp() * 1000)


def url_refusal(url: str) -> Optional[str]:
    """Why a request must not be made (fail closed), else None."""
    period = key_period_ms(url)
    if period is None:
        return "NO_PERIOD_IN_NAME"
    return protected_overlap(*period)


def guard_fetch(fetch: "Fetch") -> "Fetch":
    """The request gate: every URL is checked before the underlying fetch is called."""
    async def guarded(url: str):
        why = url_refusal(url)
        if why is not None:
            raise ProtectedObjectRefused(f"{why}: {url.rsplit('/', 1)[-1]}")
        return await fetch(url)
    return guarded


KLINE_HEADER = ("open_time", "open", "high", "low", "close", "volume", "close_time", "quote_volume",
                "count", "taker_buy_volume", "taker_buy_quote_volume", "ignore")


class HistoryDataError(RuntimeError):
    pass


@dataclass(frozen=True)
class VisionObject:
    key: str            # path below VISION_ROOT
    kind: str           # klines_monthly | klines_daily | metrics_daily
    period_end: date    # last calendar day covered by the object
    period_start: Optional[date] = None   # first calendar day covered (None: same as period_end)

    @property
    def url(self) -> str:
        return f"{VISION_ROOT}/{self.key}"

    @property
    def period_ms(self) -> tuple:
        """[first day 00:00 UTC, day after the last 00:00 UTC) in ms."""
        a = self.period_start or self.period_end
        z = self.period_end + timedelta(days=1)
        return (int(datetime(a.year, a.month, a.day, tzinfo=timezone.utc).timestamp() * 1000),
                int(datetime(z.year, z.month, z.day, tzinfo=timezone.utc).timestamp() * 1000))


def object_protected(obj: VisionObject) -> Optional[str]:
    """The protected window an object's period intersects (the object is then never requested)."""
    return protected_overlap(*obj.period_ms)


def klines_monthly(y: int, m: int) -> VisionObject:
    last = (date(y + (m == 12), m % 12 + 1, 1) - timedelta(days=1))
    return VisionObject(f"monthly/klines/{SYMBOL}/5m/{SYMBOL}-5m-{y:04d}-{m:02d}.zip", "klines_monthly", last,
                        date(y, m, 1))


def klines_daily(d: date) -> VisionObject:
    return VisionObject(f"daily/klines/{SYMBOL}/5m/{SYMBOL}-5m-{d.isoformat()}.zip", "klines_daily", d)


def metrics_daily(d: date) -> VisionObject:
    return VisionObject(f"daily/metrics/{SYMBOL}/{SYMBOL}-metrics-{d.isoformat()}.zip", "metrics_daily", d)


def _months(start: date, end_exclusive: date) -> list:
    out, y, m = [], start.year, start.month
    while date(y, m, 1) < end_exclusive:
        out.append((y, m))
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def plan_objects(today: date, *, klines_start: date = KLINES_START,
                 metrics_start: date = METRICS_START) -> tuple:
    """(planned, rejected) as of `today` (UTC). Planned: monthly klines for complete months,
    daily klines for the current month up to yesterday, daily metrics up to yesterday. Rejected:
    every object whose period intersects a protected window; it is never requested. A complete
    month that intersects one is replaced by its daily objects that do not."""
    planned: list = []
    rejected: list = []

    def take(o: VisionObject) -> None:
        (rejected if object_protected(o) else planned).append(o)

    month_start = today.replace(day=1)
    for y, m in _months(klines_start, month_start):
        mo = klines_monthly(y, m)
        if object_protected(mo) is None:
            planned.append(mo)
            continue
        rejected.append(mo)
        for d in _days(mo):
            if d >= klines_start:
                take(klines_daily(d))
    d = max(month_start, klines_start)
    while d < today:
        take(klines_daily(d))
        d += timedelta(days=1)
    d = metrics_start
    while d < today:
        take(metrics_daily(d))
        d += timedelta(days=1)
    return planned, rejected


def planned_objects(today: date, *, klines_start: date = KLINES_START,
                    metrics_start: date = METRICS_START) -> list:
    return plan_objects(today, klines_start=klines_start, metrics_start=metrics_start)[0]


def _days(month_obj: VisionObject) -> list:
    first = month_obj.period_start or month_obj.period_end.replace(day=1)
    return [first + timedelta(days=k) for k in range((month_obj.period_end - first).days + 1)]


def daily_fallback(obj: VisionObject) -> list:
    """Daily kline objects that stand in for a monthly object that is not published yet; a day
    that intersects a protected window is left out whole."""
    return [o for o in (klines_daily(d) for d in _days(obj)) if object_protected(o) is None]


# ---- parsing (pure) -------------------------------------------------------------------
def _csv_text(zip_bytes: bytes) -> str:
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as z:
        names = [n for n in z.namelist() if n.endswith(".csv")]
        if len(names) != 1:
            raise HistoryDataError(f"expected one csv member, got {names!r}")
        return z.read(names[0]).decode("utf-8")


def _ms(raw: str) -> int:
    v = int(float(raw))
    if v > 10**14:            # microseconds (Binance moved some series to µs in 2025)
        v //= 1000
    return v


def parse_klines(zip_bytes: bytes) -> list:
    """Rows of a 5m kline object, with or without the header line."""
    rows = []
    for rec in csv.reader(io.StringIO(_csv_text(zip_bytes))):
        if not rec or not rec[0].strip():
            continue
        if not rec[0].strip().lstrip("-").isdigit():
            continue                       # header
        if len(rec) < 11:
            raise HistoryDataError(f"kline row has {len(rec)} fields")
        open_ms = _ms(rec[0])
        if open_ms % 300_000:
            raise HistoryDataError(f"kline open_time {open_ms} is not on the 5m grid")
        o, h, l, c = (float(rec[k]) for k in (1, 2, 3, 4))
        if not (h >= max(o, c, l) and l <= min(o, c) and l > 0):
            raise HistoryDataError(f"kline OHLC inconsistent at {open_ms}")
        rows.append({"open_time_ms": open_ms, "open": o, "high": h, "low": l, "close": c,
                     "volume": float(rec[5]), "quote_volume": float(rec[7]),
                     "trades": int(float(rec[8])), "taker_buy_quote": float(rec[10])})
    return rows


def _ratio(raw: Optional[str]) -> Optional[float]:
    v = (raw or "").strip().strip('"')
    try:
        x = float(v) if v else None
    except ValueError:
        return None
    return x if x is not None and x > 0 else None


def parse_metrics(zip_bytes: bytes) -> list:
    """5m OI rows (ts = Vision create_time, base BTC and USD) with the global long/short account
    ratio (`count_long_short_ratio`, None when absent). Rows without OI are skipped."""
    rows = []
    reader = csv.DictReader(io.StringIO(_csv_text(zip_bytes)))
    for rec in reader:
        raw = (rec.get("create_time") or "").strip()
        oi, oiv = (rec.get("sum_open_interest") or "").strip(), (rec.get("sum_open_interest_value") or "").strip()
        if not raw or not oi:
            continue
        ts = datetime.strptime(raw, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
        ms = int(ts.timestamp() * 1000)
        if ms % 300_000:
            continue                       # off-grid snapshots are not used
        rows.append({"ts_ms": ms, "oi_base": float(oi), "oi_usd": float(oiv) if oiv else None,
                     "ls_account_ratio": _ratio(rec.get("count_long_short_ratio"))})
    return rows


def checksum_of(checksum_text: str) -> str:
    token = (checksum_text or "").strip().split()
    if not token or len(token[0]) != 64:
        raise HistoryDataError("malformed CHECKSUM object")
    return token[0].lower()


# ---- network --------------------------------------------------------------------------
Fetch = Callable[[str], Awaitable[Optional[bytes]]]


async def _aiohttp_fetch(session, url: str, *, attempts: int = 3) -> Optional[bytes]:
    delay = 2.0
    for k in range(attempts):
        try:
            async with session.get(url) as resp:
                if resp.status == 404:
                    return None
                if resp.status >= 500 and k + 1 < attempts:
                    raise HistoryDataError(f"HTTP {resp.status}")
                resp.raise_for_status()
                return await resp.read()
        except Exception:  # noqa: BLE001 - retried, then raised
            if k + 1 >= attempts:
                raise
            await asyncio.sleep(delay)
            delay *= 2
    return None


async def _fetch_verified(fetch: Fetch, obj: VisionObject) -> tuple:
    """(zip bytes, sha256) or (None, None) when the object does not exist (404)."""
    body = await fetch(obj.url)
    if body is None:
        return None, None
    chk = await fetch(obj.url + ".CHECKSUM")
    sha = hashlib.sha256(body).hexdigest()
    if chk is None:
        raise HistoryDataError(f"CHECKSUM missing for {obj.key}")
    if checksum_of(chk.decode("utf-8", "replace")) != sha:
        raise HistoryDataError(f"checksum mismatch for {obj.key}")
    return body, sha


def _needs_fetch(obj: VisionObject, ledger: dict, today: date) -> bool:
    rec = ledger.get(obj.key)
    if rec is None:
        return True
    if rec["status"] == "OK":
        return False
    young = (today - obj.period_end).days <= MISSING_RETRY_DAYS
    return young or int(rec["attempts"]) < MISSING_MAX_ATTEMPTS


async def sync_history(store, *, now: datetime, fetch: Optional[Fetch] = None,
                       max_objects: Optional[int] = None, concurrency: int = DEFAULT_CONCURRENCY,
                       klines_start: date = KLINES_START, metrics_start: date = METRICS_START) -> dict:
    """Fetch, verify, parse and upsert every planned object that the ledger does not hold.

    Resumable: interrupted runs leave OK objects in the ledger and the next run continues.
    `max_objects` bounds one run (None = everything)."""
    from storage.beta_v0_store import HISTORY_LOCK_KEY
    today = now.astimezone(timezone.utc).date()
    report = {"status": "OK", "planned": 0, "fetched": 0, "ok": 0, "missing": 0, "bad": 0, "fallback_daily": 0,
              "bars_written": 0, "oi_written": 0, "protected_rejected": 0, "protected_rejected_keys": [],
              "errors": []}
    async with store.advisory_lock(HISTORY_LOCK_KEY) as acquired:
        if not acquired:
            return {"status": "BUSY"}
        session = None
        if fetch is None:
            import aiohttp
            session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=120),
                                            headers={"User-Agent": "signalbot-beta-history/1"})
            fetch = lambda url: _aiohttp_fetch(session, url)  # noqa: E731
        fetch = guard_fetch(fetch)              # every request URL is checked before it is made
        try:
            async with store.connect() as conn:
                ledger = await conn.hist_object_ledger()
            planned, rejected = plan_objects(today, klines_start=klines_start, metrics_start=metrics_start)
            report["protected_rejected"] = len(rejected)
            report["protected_rejected_keys"] = [o.key for o in rejected]
            plan = [o for o in planned if _needs_fetch(o, ledger, today)]
            report["planned"] = len(plan)
            if max_objects is not None:
                plan = plan[: int(max_objects)]
            sem = asyncio.Semaphore(max(1, int(concurrency)))

            async def one(obj: VisionObject) -> list:
                async with sem:
                    why = object_protected(obj)
                    if why is not None:             # never reached through the plan; refused, not fetched
                        report["errors"].append(f"{obj.key}: ProtectedObjectRefused: {why}")
                        return []
                    try:
                        body, sha = await _fetch_verified(fetch, obj)
                    except Exception as exc:  # noqa: BLE001 - one object never stops the sync
                        report["errors"].append(f"{obj.key}: {type(exc).__name__}: {str(exc)[:120]}")
                        return []
                    report["fetched"] += 1
                    extra = []
                    rows = None
                    if body is not None:
                        try:                    # parse first: a malformed archive is BAD, a DB error is not
                            if obj.kind.startswith("klines"):
                                rows = drop_protected(parse_klines(body), "open_time_ms")
                            else:
                                rows = drop_protected(parse_metrics(body), "ts_ms")
                        except Exception as exc:  # noqa: BLE001 - a malformed object never stops the sync
                            # BAD is retried like MISSING, so a fixed upstream file is picked up and a
                            # broken one stops costing runs; nothing of it is stored
                            report["errors"].append(f"{obj.key}: {type(exc).__name__}: {str(exc)[:120]}")
                            report["bad"] += 1
                            try:
                                async with store.connect() as conn:
                                    await conn.record_hist_object(obj.key, obj.kind, status="BAD", now=now)
                            except Exception:  # noqa: BLE001
                                pass
                            return []
                    try:
                        async with store.connect() as conn:
                            async with conn.transaction():
                                if body is None:
                                    await conn.record_hist_object(obj.key, obj.kind, status="MISSING", now=now)
                                    report["missing"] += 1
                                    if obj.kind == "klines_monthly" and (today - obj.period_end).days <= 40:
                                        extra = [d for d in daily_fallback(obj)
                                                 if _needs_fetch(d, ledger, today)]
                                        report["fallback_daily"] += len(extra)
                                    return extra
                                if obj.kind.startswith("klines"):
                                    report["bars_written"] += await conn.upsert_hist_bars(rows, fetched_at=now)
                                else:
                                    report["oi_written"] += await conn.upsert_hist_oi(rows, fetched_at=now)
                                await conn.record_hist_object(obj.key, obj.kind, status="OK", sha256=sha,
                                                              rows=len(rows), now=now)
                                report["ok"] += 1
                    except Exception as exc:  # noqa: BLE001 - one object never stops the sync
                        report["errors"].append(f"{obj.key}: {type(exc).__name__}: {str(exc)[:120]}")
                        return []
                    return extra

            pending = list(plan)
            while pending:
                results = await asyncio.gather(*(one(o) for o in pending))
                pending = [o for extra in results for o in extra]
            async with store.connect() as conn:
                bounds = await conn.hist_bounds()
                await conn.record_health("history_sync", now=datetime.now(timezone.utc),
                                         success=not report["errors"],
                                         detail={k: v for k, v in report.items() if isinstance(v, int)})
            report.update(bounds)
            if report["errors"]:
                report["status"] = "PARTIAL"
            return report
        finally:
            if session is not None:
                await session.close()


# ---- local archives (tests, offline calibration) -------------------------------------
def rows_from_local_zips(paths: Iterable[str]) -> list:
    """Parse 5m kline zips already on disk (e.g. the repo's durable research copies)."""
    rows = []
    for p in sorted(paths):
        with open(p, "rb") as fh:
            rows.extend(parse_klines(fh.read()))
    rows.sort(key=lambda r: r["open_time_ms"])
    return rows
