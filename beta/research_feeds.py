"""Read-only public market feeds for the research-evidence engine (owner task, 2026-10-04).

Each feed exists because the frozen state of a closed research unit needs it live
(docs/research/RESEARCH_EVIDENCE_INTEGRATION_V1.md):

- Binance USD-M BTCUSDT `/futures/data/openInterestHist` and `globalLongShortAccountRatio` (5m):
  the live tail of the Vision `metrics` series the research used (DH3-P1/P2 open interest, DH3-P3
  crowd positioning, MARKET-01/02 open interest). Same label `ts`; used from ts + 5m on.
- Deribit BTC DVOL hourly candles (`public/get_volatility_index_data`, resolution 3600): the DH3-O
  research source itself.
- Binance USD-M BTCUSDT REST depth (1000 levels a side): notional within ±1 % of the mid (DH3-L).
  A side is stored only when the snapshot reaches 1 % on that side (or returned the whole side):
  a partial sum is never stored.
- Binance spot BTCUSDT 5m klines from the public market-data API (DH2-L1, DH2-B2).
- Stress hours (`run_stress_job`, hourly): an hour whose perp log range reaches the frozen DH3-S cut
  gets the 1-second spot/perp lead score and the count of perp aggTrades >= 1M USD, from the public
  aggTrades of both venues, computed exactly as `scripts/research/dh3/aggtrades.py`.

Public endpoints only: no key, no account endpoint, no order endpoint, nothing executes. Every row
is dropped when it falls inside a protected window (the E1-RUN-001 holdout) before it is stored.
Parsing and feature code is pure; `run_feeds_job` / `run_stress_job` do the I/O.
"""
from __future__ import annotations

import asyncio
import logging
import math
from datetime import datetime, timedelta, timezone
from typing import Any, Awaitable, Callable, Iterable, Mapping, Optional, Sequence

import numpy as np

logger = logging.getLogger("beta.research_feeds")

FEEDS_VERSION = "BETA_RESEARCH_FEEDS_V1"
SYMBOL = "BTCUSDT"
FAPI = "https://fapi.binance.com"
SPOT_API = "https://data-api.binance.vision"          # Binance's public market-data-only endpoint
DERIBIT_DVOL = "https://www.deribit.com/api/v2/public/get_volatility_index_data"
BAR_MS = 300_000
HOUR_MS = 3_600_000
METRICS_PAGE = 500                                     # /futures/data rows per request
METRICS_BACKFILL = timedelta(days=30)                  # the endpoint serves the latest 30 days only
DVOL_BACKFILL = timedelta(hours=72)
SPOT_BACKFILL = timedelta(days=3)
DEPTH_LIMIT = 1000
DEPTH_BAND_PCT = 1.0
STRESS_LOOKBACK_H = 6
AGG_PAGE = 1000
MAX_AGG_PAGES = 1500                                   # per venue and hour; beyond it the hour is INCOMPLETE
LEAD_LAGS_S = (1, 2, 3)                                # DH3 constants.LEAD_LAGS_S
LARGE_PRINT_USD = 1_000_000.0                          # DH3 constants.LARGE_PRINT_USD
MIN_TRADES = 100                                       # DH3 aggtrades.process_month
DEFINITION_TOL = 1e-6                                  # relative REST vs Vision difference allowed (same digits)
DEFINITION_MIN_OVERLAP = 100

FetchJson = Callable[[str, Mapping[str, Any]], Awaitable[Any]]


class RateLimited(RuntimeError):
    """HTTP 418 / 429: stop calling this host for this run."""


def _protected(ms: int) -> bool:
    from .history_data import in_protected_window
    return in_protected_window(int(ms))


def _ms(dt: datetime) -> int:
    return int(dt.timestamp() * 1000)


def _f(v) -> Optional[float]:
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


# ---- parsing (pure) ---------------------------------------------------------------------
def parse_oi_hist(rows: Iterable[Mapping[str, Any]]) -> dict:
    out = {}
    for r in rows or ():
        t = int(r.get("timestamp", -1))
        oi = _f(r.get("sumOpenInterest"))
        if t % BAR_MS or oi is None or oi < 0:
            continue
        out[t] = {"oi_base": oi, "oi_usd": _f(r.get("sumOpenInterestValue"))}
    return out


def parse_ls_ratio(rows: Iterable[Mapping[str, Any]]) -> dict:
    out = {}
    for r in rows or ():
        t = int(r.get("timestamp", -1))
        x = _f(r.get("longShortRatio"))
        if t % BAR_MS or x is None or x <= 0:
            continue
        out[t] = x
    return out


def merge_metrics(oi: Mapping[int, Mapping], ls: Mapping[int, float], *, now_ms: int) -> list:
    """Rows by label; a label is kept only when its value was already published (label + 5m <= now)
    and it lies outside every protected window."""
    out = []
    for t in sorted(set(oi) | set(ls)):
        if t + BAR_MS > now_ms or _protected(t):
            continue
        o = oi.get(t) or {}
        out.append({"ts_ms": t, "oi_base": o.get("oi_base"), "oi_usd": o.get("oi_usd"), "ls_account_ratio": ls.get(t)})
    return out


def parse_dvol(payload: Mapping[str, Any], *, now_ms: int) -> list:
    """Closed hourly candles [t, o, h, l, c] from a Deribit response."""
    data = ((payload or {}).get("result") or {}).get("data") or []
    out = []
    for rec in data:
        if len(rec) < 5:
            continue
        t = int(rec[0])
        vals = [_f(x) for x in rec[1:5]]
        if t % HOUR_MS or t + HOUR_MS > now_ms or any(v is None or v <= 0 for v in vals) or _protected(t):
            continue
        out.append({"t_ms": t, "open": vals[0], "high": vals[1], "low": vals[2], "close": vals[3]})
    return out


def depth_band(book: Mapping[str, Any], *, band_pct: float = DEPTH_BAND_PCT,
               now_ms: Optional[int] = None) -> Optional[dict]:
    """Notional within ±band_pct of the mid from a REST depth snapshot. A side is None unless the
    snapshot's deepest level on that side lies at least band_pct from the mid: the levels inside
    the band are then all in the snapshot and the sum is exact; otherwise it would be partial."""
    bids = [(float(p), float(q)) for p, q in (book.get("bids") or ())]
    asks = [(float(p), float(q)) for p, q in (book.get("asks") or ())]
    if not bids or not asks or bids[0][0] <= 0 or asks[0][0] <= bids[0][0]:
        return None
    mid = (bids[0][0] + asks[0][0]) / 2.0
    lo, hi = mid * (1 - band_pct / 100.0), mid * (1 + band_pct / 100.0)
    bid_reach = (mid - bids[-1][0]) / mid * 100.0
    ask_reach = (asks[-1][0] - mid) / mid * 100.0
    ts = book.get("T") or book.get("E") or now_ms
    if ts is None:
        return None
    return {"ts_ms": int(ts), "mid": mid,
            "bid1_usd": sum(p * q for p, q in bids if p >= lo) if bid_reach >= band_pct else None,
            "ask1_usd": sum(p * q for p, q in asks if p <= hi) if ask_reach >= band_pct else None,
            "bid_reach_pct": bid_reach, "ask_reach_pct": ask_reach, "levels": min(len(bids), len(asks))}


def parse_spot_klines(rows: Iterable[Sequence[Any]], *, now_ms: int) -> list:
    out = []
    for r in rows or ():
        if len(r) < 11:
            continue
        t, close_t = int(r[0]), int(r[6])
        if t % BAR_MS or close_t >= now_ms or _protected(t):
            continue
        o, h, lo, c = (_f(r[k]) for k in (1, 2, 3, 4))
        if None in (o, h, lo, c) or lo <= 0:
            continue
        out.append({"open_time_ms": t, "open": o, "high": h, "low": lo, "close": c, "volume": _f(r[5]) or 0.0,
                    "quote_volume": _f(r[7]) or 0.0, "taker_buy_quote": _f(r[10]) or 0.0, "trades": int(r[8])})
    return out


def hour_ranges(klines_1h: Iterable[Sequence[Any]], *, now_ms: int) -> dict:
    """{hour start: log(high / low)} of closed perp 1h klines (= max/min of its 12 5m bars)."""
    out = {}
    for r in klines_1h or ():
        t = int(r[0])
        hi, lo = _f(r[2]), _f(r[3])
        if t % HOUR_MS or t + HOUR_MS > now_ms or hi is None or lo is None or lo <= 0 or hi < lo:
            continue
        out[t] = math.log(hi / lo)
    return out


# ---- DH3-S features (pure; identical to scripts/research/dh3/aggtrades.py) --------------
def second_grid(times: np.ndarray, prices: np.ndarray, hour: int) -> np.ndarray:
    """Last trade price at the end of each second of the hour (leading seconds take the first price)."""
    order = np.argsort(times, kind="mergesort")
    times, prices = times[order], prices[order]
    sec = ((times - hour) // 1000).astype(np.int64)
    grid = np.full(3600, np.nan)
    last_idx = np.flatnonzero(np.r_[sec[1:] != sec[:-1], True])
    grid[sec[last_idx]] = prices[last_idx]
    if np.isnan(grid[0]):
        grid[0] = prices[0]
    idx = np.where(np.isfinite(grid), np.arange(3600), 0)
    return grid[np.maximum.accumulate(idx)]


def lead_score(perp_grid: np.ndarray, spot_grid: np.ndarray) -> Optional[float]:
    rp, rs = np.diff(np.log(perp_grid)), np.diff(np.log(spot_grid))
    if np.std(rp) == 0 or np.std(rs) == 0:
        return None
    total = 0.0
    for k in LEAD_LAGS_S:
        a = np.corrcoef(rp[:-k], rs[k:])[0, 1]
        b = np.corrcoef(rs[:-k], rp[k:])[0, 1]
        if not (np.isfinite(a) and np.isfinite(b)):
            return None
        total += a - b
    return float(total)


def stress_features(perp: Mapping[str, np.ndarray], spot: Mapping[str, np.ndarray], hour: int) -> dict:
    """{status, lead_score, n_large_perp, n_perp_trades, n_spot_trades} for one stress hour."""
    npt, nst = int(perp["t"].size), int(spot["t"].size)
    if npt < MIN_TRADES or nst < MIN_TRADES:
        return {"status": "INSUFFICIENT_TRADES", "lead_score": None, "n_large_perp": None,
                "n_perp_trades": npt, "n_spot_trades": nst}
    score = lead_score(second_grid(perp["t"], perp["p"], hour), second_grid(spot["t"], spot["p"], hour))
    n_large = int(np.sum(perp["p"] * perp["q"] >= LARGE_PRINT_USD))
    return {"status": "OK", "lead_score": score, "n_large_perp": n_large, "n_perp_trades": npt, "n_spot_trades": nst}


def trades_in_hour(pages: Iterable[Sequence[Mapping[str, Any]]], hour: int) -> dict:
    t, p, q = [], [], []
    for page in pages:
        for r in page:
            tt = int(r["T"])
            if hour <= tt < hour + HOUR_MS:
                t.append(tt)
                p.append(float(r["p"]))
                q.append(float(r["q"]))
    return {"t": np.asarray(t, dtype=np.int64), "p": np.asarray(p, dtype=float), "q": np.asarray(q, dtype=float)}


# ---- REST vs Vision definition check (pure) ---------------------------------------------
def definition_check(feed: Sequence[Mapping[str, Any]], vision: Sequence[Mapping[str, Any]]) -> dict:
    """Do the REST rows carry the Vision series under the same labels? For each field, the share
    of overlapping labels whose values agree within DEFINITION_TOL, at offsets -5m / 0 / +5m.
    OK only at offset 0 with >= DEFINITION_MIN_OVERLAP labels and >= 95 % agreement."""
    out = {}
    for field in ("oi_base", "ls_account_ratio"):
        f = {int(r["ts_ms"]): r.get(field) for r in feed if r.get(field) is not None}
        v = {int(r["ts_ms"]): r.get(field) for r in vision if r.get(field) is not None}
        best = None
        for off in (0, -BAR_MS, BAR_MS):                 # offset 0 first: another one wins only if strictly better
            common = [t for t in f if (t + off) in v]
            if not common:
                continue
            agree = sum(1 for t in common if abs(f[t] - v[t + off]) <= DEFINITION_TOL * max(abs(v[t + off]), 1e-12))
            cand = {"offset_ms": off, "overlap": len(common), "agree_share": agree / len(common)}
            if best is None or cand["agree_share"] > best["agree_share"]:
                best = cand
        if best is None or best["overlap"] < DEFINITION_MIN_OVERLAP:
            out[field] = {"status": "PENDING", **(best or {"overlap": 0})}
        elif best["offset_ms"] == 0 and best["agree_share"] >= 0.95:
            out[field] = {"status": "OK", **best}
        else:
            out[field] = {"status": "FAILED", **best}
    return out


# ---- schema readiness (read-only; deploy plan PREREQ-1) ---------------------------------
# The core DB role applies storage/beta_v0_schema.sql (bot start-up, the history and detector
# commands). A feed job never runs DDL: it reads the catalog to verify that every table, column,
# key and check it uses exists and that the connected role holds the grants it needs, and it
# refuses to run otherwise (SCHEMA_NOT_READY, nothing written). With an expected role set (the feed
# units set it), another connected role is refused (WRONG_DB_ROLE): no silent run as the core role.
FEED_TABLE_COLUMNS = {
    "beta_feed_metrics_5m": ("ts", "oi_base", "oi_usd", "ls_account_ratio", "source", "fetched_at"),
    "beta_feed_dvol_1h": ("hour_start", "open", "high", "low", "close", "source", "fetched_at"),
    "beta_feed_spot_5m": ("open_time", "open", "high", "low", "close", "volume", "quote_volume",
                          "taker_buy_quote", "trades", "source", "fetched_at"),
    "beta_feed_depth": ("ts", "mid", "bid1_usd", "ask1_usd", "bid_reach_pct", "ask_reach_pct", "levels", "source",
                        "fetched_at"),
    "beta_feed_stress_hours": ("hour_start", "perp_log_range", "status", "lead_score", "n_large_perp",
                               "n_perp_trades", "n_spot_trades", "computed_at"),
    # first_run_at: written by every record_health since the A3/A5 review (review of #345)
    "beta_runtime_health": ("component", "last_run_at", "last_success_at", "last_error_type", "detail",
                            "first_run_at"),
    "beta_hist_oi_5m": ("ts", "oi_base", "ls_account_ratio"),
}
FEED_TABLE_CHECKS = {"beta_feed_depth": ("ck_beta_feed_depth_cover",),
                     "beta_feed_stress_hours": ("ck_beta_feed_stress_ok",)}
# per job: {table: table privileges}; every written table needs its primary key (ON CONFLICT)
FEED_JOB_GRANTS = {
    "feeds": {"beta_feed_metrics_5m": ("SELECT", "INSERT", "UPDATE"),
              "beta_feed_dvol_1h": ("SELECT", "INSERT", "UPDATE"),
              "beta_feed_spot_5m": ("SELECT", "INSERT", "UPDATE"),
              "beta_feed_depth": ("SELECT", "INSERT"),
              "beta_runtime_health": ("SELECT", "INSERT", "UPDATE")},
    "stress": {"beta_feed_stress_hours": ("SELECT", "INSERT", "UPDATE"),
               "beta_runtime_health": ("SELECT", "INSERT", "UPDATE")},
}
# per job: columns read from tables the job does not write (column grants are enough)
FEED_JOB_COLUMN_READS = {"feeds": {"beta_hist_oi_5m": ("ts", "oi_base", "ls_account_ratio")}, "stress": {}}


async def feed_schema_readiness(conn, job: str, *, expected_role: Optional[str] = None) -> dict:
    """{"ready", "status", "db_role", "missing"} for `job` ("feeds" | "stress"). Catalog reads only."""
    grants, reads = FEED_JOB_GRANTS[job], FEED_JOB_COLUMN_READS[job]
    role = await conn.db_role()
    if expected_role and role["name"] != expected_role:
        return {"ready": False, "status": "WRONG_DB_ROLE", "db_role": role["name"],
                "missing": [f"role:{expected_role}"]}
    tables = sorted(set(grants) | set(reads))
    cat = await conn.catalog_tables(tables)
    missing: list = []
    present = []
    for t in tables:
        info = cat.get(t) or {"present": False}
        if not info["present"]:
            missing.append(f"table:{t}")
            continue
        present.append(t)
        missing += [f"column:{t}.{c}" for c in FEED_TABLE_COLUMNS[t] if c not in info["columns"]]
        missing += [f"check:{t}.{k}" for k in FEED_TABLE_CHECKS.get(t, ()) if k not in info["constraints"]]
        if t in grants and not info["has_pk"]:
            missing.append(f"primary_key:{t}")
    table_priv = await conn.table_privileges([(t, p) for t in present if t in grants for p in grants[t]])
    missing += [f"grant:{p}:{t}" for (t, p), ok in sorted(table_priv.items()) if not ok]
    col_priv = await conn.column_privileges([(t, c, "SELECT") for t in present if t in reads for c in reads[t]
                                             if c in cat[t]["columns"]])
    missing += [f"grant:SELECT:{t}.{c}" for (t, c, _p), ok in sorted(col_priv.items()) if not ok]
    return {"ready": not missing, "status": "OK" if not missing else "SCHEMA_NOT_READY", "db_role": role["name"],
            "missing": missing}


# the health row a refused job leaves (A3 review: a refusal must reach the owner's alerts)
JOB_HEALTH = {"feeds": "research_feeds", "stress": "research_stress_hours"}


async def _readiness(store, job: str, expected_role: Optional[str], now: datetime) -> Optional[dict]:
    """None when the job may run; otherwise the refusal report (logged; no feed data written). The
    refusal is recorded as a failed run of the job's health row when the role may write it, so the
    owner's FEEDS_FAILING / STRESS_HOURS_FAILING alert follows by the job's cadence."""
    async with store.connect() as conn:
        ready = await feed_schema_readiness(conn, job, expected_role=expected_role)
    if ready["ready"]:
        return None
    logger.error("%s job refused: %s (%s)", job, ready["status"], ", ".join(ready["missing"][:12]))
    try:
        async with store.connect() as conn:
            await conn.record_health(JOB_HEALTH[job], now=now, success=False,
                                     error_type=ready["status"])
    except Exception as exc:  # noqa: BLE001 - without the grant the refusal stays in the unit's log
        logger.warning("%s refusal not recorded: %s", job, type(exc).__name__)
    return {"status": ready["status"], "version": FEEDS_VERSION, "db_role": ready["db_role"],
            "missing": ready["missing"]}


# ---- network ----------------------------------------------------------------------------
def _session_fetch(session) -> FetchJson:
    async def fetch(url: str, params: Mapping[str, Any]):
        async with session.get(url, params=dict(params)) as resp:
            if resp.status in (418, 429):
                raise RateLimited(f"HTTP {resp.status} from {url.split('/')[2]}")
            resp.raise_for_status()
            return await resp.json()
    return fetch


async def _metrics_endpoint(fetch: FetchJson, path: str, *, start_ms: int, now_ms: int,
                            pause: Callable[[float], Awaitable[None]]) -> list:
    rows: list = []
    t = start_ms
    while t <= now_ms:
        end = min(t + METRICS_PAGE * BAR_MS - 1, now_ms)
        page = await fetch(FAPI + path, {"symbol": SYMBOL, "period": "5m", "limit": METRICS_PAGE,
                                         "startTime": t, "endTime": end})
        rows.extend(page or [])
        t = end + 1
        await pause(0.2)
    return rows


async def sync_metrics(conn, fetch: FetchJson, *, now: datetime, pause) -> dict:
    now_ms = _ms(now)
    floor = now_ms - int(METRICS_BACKFILL.total_seconds() * 1000) + 10 * 60_000
    out = {}
    raw = {}
    for field, path in (("oi_base", "/futures/data/openInterestHist"),
                        ("ls_account_ratio", "/futures/data/globalLongShortAccountRatio")):
        last = await conn.latest_feed_ts("beta_feed_metrics_5m", "ts", where=f"{field} IS NOT NULL")
        start = max(floor, (_ms(last) + BAR_MS) if last else floor)
        start -= start % BAR_MS
        raw[field] = await _metrics_endpoint(fetch, path, start_ms=start, now_ms=now_ms, pause=pause)
    rows = merge_metrics(parse_oi_hist(raw["oi_base"]), parse_ls_ratio(raw["ls_account_ratio"]), now_ms=now_ms)
    out["metrics_rows"] = await conn.upsert_feed_metrics(rows, fetched_at=now)
    return out


async def sync_dvol(conn, fetch: FetchJson, *, now: datetime) -> dict:
    now_ms = _ms(now)
    last = await conn.latest_feed_ts("beta_feed_dvol_1h", "hour_start")
    start = (_ms(last) + HOUR_MS) if last else now_ms - int(DVOL_BACKFILL.total_seconds() * 1000)
    start -= start % HOUR_MS
    if start + HOUR_MS > now_ms:
        return {"dvol_rows": 0}
    payload = await fetch(DERIBIT_DVOL, {"currency": "BTC", "start_timestamp": start, "end_timestamp": now_ms,
                                         "resolution": "3600"})
    rows = parse_dvol(payload, now_ms=now_ms)
    return {"dvol_rows": await conn.upsert_feed_dvol(rows, fetched_at=now)}


async def sync_depth(conn, fetch: FetchJson, *, now: datetime) -> dict:
    book = await fetch(FAPI + "/fapi/v1/depth", {"symbol": SYMBOL, "limit": DEPTH_LIMIT})
    row = depth_band(book or {}, now_ms=_ms(now))
    if row is None or _protected(row["ts_ms"]):
        return {"depth": "NO_SNAPSHOT"}
    await conn.insert_feed_depth(row, fetched_at=now)
    covered = row["bid1_usd"] is not None and row["ask1_usd"] is not None
    return {"depth": "COVERED" if covered else "NOT_COVERED", "depth_bid_reach_pct": round(row["bid_reach_pct"], 3),
            "depth_ask_reach_pct": round(row["ask_reach_pct"], 3)}


async def sync_spot(conn, fetch: FetchJson, *, now: datetime) -> dict:
    now_ms = _ms(now)
    last = await conn.latest_feed_ts("beta_feed_spot_5m", "open_time")
    start = (_ms(last) + BAR_MS) if last else now_ms - int(SPOT_BACKFILL.total_seconds() * 1000)
    start -= start % BAR_MS
    n = 0
    while start + BAR_MS <= now_ms:
        page = await fetch(SPOT_API + "/api/v3/klines", {"symbol": SYMBOL, "interval": "5m", "startTime": start,
                                                         "limit": 1000})
        rows = parse_spot_klines(page or [], now_ms=now_ms)
        n += await conn.upsert_feed_spot(rows, fetched_at=now)
        if not page or len(page) < 1000:
            break
        start = int(page[-1][0]) + BAR_MS
    return {"spot_rows": n}


async def run_feeds_job(store, *, now: datetime, fetch: Optional[FetchJson] = None,
                        pause: Optional[Callable[[float], Awaitable[None]]] = None,
                        expected_role: Optional[str] = None) -> dict:
    """One pass of every fast feed; a failing feed never stops the others. Records health
    `research_feeds` and the REST-vs-Vision definition check `research_feeds_definition`.
    Refuses to run (nothing written) unless `feed_schema_readiness` passes."""
    from storage.beta_v0_store import FEEDS_LOCK_KEY
    refused = await _readiness(store, "feeds", expected_role, now)
    if refused is not None:
        return refused
    pause = pause or asyncio.sleep
    report: dict = {"status": "OK", "version": FEEDS_VERSION, "errors": {}}
    async with store.advisory_lock(FEEDS_LOCK_KEY) as acquired:
        if not acquired:
            return {"status": "BUSY"}
        session = None
        if fetch is None:
            import aiohttp
            session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30),
                                            headers={"User-Agent": "signalbot-beta-feeds/1"})
            fetch = _session_fetch(session)
        try:
            for name, job in (("metrics", lambda c: sync_metrics(c, fetch, now=now, pause=pause)),
                              ("dvol", lambda c: sync_dvol(c, fetch, now=now)),
                              ("depth", lambda c: sync_depth(c, fetch, now=now)),
                              ("spot", lambda c: sync_spot(c, fetch, now=now))):
                try:
                    async with store.connect() as conn:
                        report.update(await job(conn))
                except Exception as exc:  # noqa: BLE001 - one feed never stops the others
                    report["errors"][name] = f"{type(exc).__name__}: {str(exc)[:120]}"
            async with store.connect() as conn:
                since = now - METRICS_BACKFILL
                check = definition_check(await conn.fetch_feed_metrics(start=since, end=now),
                                         await conn.fetch_hist_metrics(start=since, end=now))
                report["definition_check"] = check
                await conn.record_health("research_feeds_definition", now=now,
                                         success=all(c["status"] == "OK" for c in check.values()), detail=check)
                if report["errors"]:
                    report["status"] = "PARTIAL"
                await conn.record_health("research_feeds", now=now, success=not report["errors"],
                                         error_type=",".join(sorted(report["errors"])) or None,
                                         detail={k: v for k, v in report.items() if k not in ("definition_check",)})
            return report
        finally:
            if session is not None:
                await session.close()


# ---- stress hours (hourly; heavier) -----------------------------------------------------
async def _agg_pages(fetch: FetchJson, url: str, *, hour: int, pace_s: float, pause) -> tuple:
    """All aggTrades of [hour, hour + 1h) from one venue: (pages, complete)."""
    pages = []
    page = await fetch(url, {"symbol": SYMBOL, "startTime": hour, "endTime": hour + HOUR_MS - 1, "limit": AGG_PAGE})
    while page:
        pages.append(page)
        if int(page[-1]["T"]) >= hour + HOUR_MS - 1 or len(page) < AGG_PAGE:
            return pages, True
        if len(pages) >= MAX_AGG_PAGES:
            return pages, False
        await pause(pace_s)
        page = await fetch(url, {"symbol": SYMBOL, "fromId": int(page[-1]["a"]) + 1, "limit": AGG_PAGE})
        if page and int(page[0]["T"]) >= hour + HOUR_MS:
            return pages, True
    return pages, True


async def run_stress_job(store, *, now: datetime, cut: Optional[float] = None, fetch: Optional[FetchJson] = None,
                         pause: Optional[Callable[[float], Awaitable[None]]] = None,
                         perp_pace_s: float = 1.0, spot_pace_s: float = 0.25,
                         expected_role: Optional[str] = None) -> dict:
    """Check the last completed hours: record each one's perp log range; for a stress hour also the
    DH3-S features. Perp aggTrades are paced at about one request a second (weight 20 each).
    Refuses to run (nothing written) unless `feed_schema_readiness` passes."""
    from storage.beta_v0_store import STRESS_LOCK_KEY
    from .research_evidence import load_cuts
    refused = await _readiness(store, "stress", expected_role, now)
    if refused is not None:
        return refused
    pause = pause or asyncio.sleep
    cut = float(load_cuts()["S_STRESS_HOUR_LOG_RANGE_MIN"]) if cut is None else float(cut)
    now_ms = _ms(now)
    report: dict = {"status": "OK", "version": FEEDS_VERSION, "checked": 0, "stress": 0, "incomplete": 0}
    async with store.advisory_lock(STRESS_LOCK_KEY) as acquired:
        if not acquired:
            return {"status": "BUSY"}
        session = None
        if fetch is None:
            import aiohttp
            session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=60),
                                            headers={"User-Agent": "signalbot-beta-feeds/1"})
            fetch = _session_fetch(session)
        try:
            first = now_ms - now_ms % HOUR_MS - STRESS_LOOKBACK_H * HOUR_MS
            async with store.connect() as conn:
                known = {int(r["hour_ms"]): r["status"] for r in await conn.fetch_feed_stress_hours(
                    start=datetime.fromtimestamp(first / 1000, tz=timezone.utc), end=now)}
            k1h = await fetch(FAPI + "/fapi/v1/klines", {"symbol": SYMBOL, "interval": "1h", "startTime": first,
                                                         "limit": STRESS_LOOKBACK_H + 1})
            for hour, rng in sorted(hour_ranges(k1h or [], now_ms=now_ms).items()):
                if _protected(hour) or (hour in known and known[hour] != "INCOMPLETE"):
                    continue
                report["checked"] += 1
                row = {"hour_ms": hour, "perp_log_range": rng}
                if rng < cut:
                    row["status"] = "NOT_STRESS"
                else:
                    report["stress"] += 1
                    try:
                        perp_pages, p_ok = await _agg_pages(fetch, FAPI + "/fapi/v1/aggTrades", hour=hour,
                                                            pace_s=perp_pace_s, pause=pause)
                        spot_pages, s_ok = await _agg_pages(fetch, SPOT_API + "/api/v3/aggTrades", hour=hour,
                                                            pace_s=spot_pace_s, pause=pause)
                    except Exception as exc:  # noqa: BLE001 - the hour stays INCOMPLETE and is retried later
                        report["errors"] = f"{type(exc).__name__}: {str(exc)[:120]}"
                        p_ok = s_ok = False
                        perp_pages = spot_pages = []
                    if not (p_ok and s_ok):
                        row["status"] = "INCOMPLETE"
                        report["incomplete"] += 1
                    else:
                        row.update(stress_features(trades_in_hour(perp_pages, hour), trades_in_hour(spot_pages, hour),
                                                   hour))
                async with store.connect() as conn:
                    await conn.upsert_feed_stress_hour(row, now=now)
                if report.get("errors"):
                    break                                # a failing host is not called again in this run
            if report.get("errors"):
                report["status"] = "PARTIAL"
            async with store.connect() as conn:
                await conn.record_health("research_stress_hours", now=now, success="errors" not in report,
                                         error_type=report.get("errors", "").split(":", 1)[0] or None,
                                         detail={k: v for k, v in report.items() if isinstance(v, (int, str))})
            return report
        except Exception as exc:
            # the run itself failed (the 1h klines or the database): health says so, then the unit fails
            logger.warning("stress-hour job failed: %s", type(exc).__name__)
            try:
                async with store.connect() as conn:
                    await conn.record_health("research_stress_hours", now=now, success=False,
                                             error_type=type(exc).__name__)
            except Exception as record_exc:  # noqa: BLE001 - the original error is the one to raise
                logger.warning("stress-hour health record failed: %s", type(record_exc).__name__)
            raise
        finally:
            if session is not None:
                await session.close()
