"""Outcome-blind BitMEX XBTUSD pre-2020 source census.

Calendar/schema feasibility only. Does not compute D2 rule performance,
severity differences, randomization p-values, or confirmation classification.
Does not open Binance 2025/2026 prices.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

UTC = timezone.utc

PARSER_VERSION = "D2_BITMEX_PRE2020_PARSER_V1"
INSTRUMENT = "XBTUSD"
INSTRUMENT_TYP = "FFWCSX"  # perpetual swap
LISTING_UTC = datetime(2016, 5, 13, 12, 0, tzinfo=UTC)
PRE2020_END_EXCLUSIVE = datetime(2020, 1, 1, 0, 0, tzinfo=UTC)
BAR_MS = 300_000
RV_RETURN_COUNT = 288
FUTURE_BARS = 288
RV_TRAILING_WINDOW = 250
DECISION_HOUR = 0
DECISION_MINUTE = 5

BITMEX_REST = "https://www.bitmex.com/api/v1"
BITMEX_BUCKETED = f"{BITMEX_REST}/trade/bucketed"
BITMEX_INSTRUMENT = f"{BITMEX_REST}/instrument"
BITMEX_BUCKETED_DOCS = "https://docs.bitmex.com/api-explorer/get-trade-bucketed"
BITMEX_LAUNCH_POST = (
    "https://www.bitmex.com/blog/announcing-the-launch-of-the-perpetual-xbtusd-leveraged-swap"
)
BITMEX_CANDLE_SUPPORT = (
    "https://support.bitmex.com/hc/en-gb/articles/6299353754909-Where-Can-I-Find-Historical-Candlestick-Data"
)
BITMEX_PUBLIC_ARCHIVE = "https://public.bitmex.com/"
USER_AGENT = "signalbot-d2-bitmex-pre2020-feasibility/1.0"

ARTIFACT_REL = "artifacts/research_data/D2_BITMEX_PRE2020_XBTUSD"
AUTHORITY_REL = "docs/research_data/D2_BITMEX_PRE2020_SOURCE_AUTHORITY.json"

# Official: bucket timestamp is the END of the period.
TIMESTAMP_SEMANTICS = "BUCKET_END"


class BitmexSchemaError(RuntimeError):
    """Duplicate, non-monotonic, or otherwise illegal source rows."""


class ProtectedBinanceRefused(RuntimeError):
    """Binance protected 2025/2026 paths are out of scope."""


class D2OutcomeRefused(RuntimeError):
    """D2 scientific outcomes are not computed in this unit."""


def utc_ms(moment: datetime) -> int:
    if moment.tzinfo is None:
        raise ValueError("NAIVE_DATETIME")
    return int(moment.timestamp() * 1000)


def from_ms(ms: int) -> datetime:
    return datetime.fromtimestamp(ms / 1000.0, tz=UTC)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def parse_bitmex_timestamp(value: str) -> datetime:
    text = str(value).replace("Z", "+00:00")
    moment = datetime.fromisoformat(text)
    if moment.tzinfo is None:
        raise BitmexSchemaError(f"NAIVE_BITMEX_TIMESTAMP:{value}")
    return moment.astimezone(UTC)


def bitmex_end_ts_to_open_ms(end_ts: datetime) -> int:
    end_ms = utc_ms(end_ts)
    if end_ms % BAR_MS != 0:
        raise BitmexSchemaError(f"NOT_5M_ALIGNED_END:{end_ts.isoformat()}")
    open_ms = end_ms - BAR_MS
    if open_ms % BAR_MS != 0:
        raise BitmexSchemaError(f"NOT_5M_ALIGNED_OPEN:{open_ms}")
    return int(open_ms)


def is_december_31(moment: datetime) -> bool:
    return moment.month == 12 and moment.day == 31


def is_pre2020_decision_clock(moment: datetime) -> bool:
    return (
        moment.hour == DECISION_HOUR
        and moment.minute == DECISION_MINUTE
        and moment.second == 0
        and moment.microsecond == 0
        and moment.tzinfo is not None
        and not is_december_31(moment)
        and moment < PRE2020_END_EXCLUSIVE
    )


def refuse_binance_protected_path(path: Path) -> None:
    text = str(path)
    if "2025-" in text or "2026-" in text:
        if text.endswith(".parquet") or text.endswith(".zip") or "/canonical/" in text.replace("\\", "/"):
            raise ProtectedBinanceRefused(f"PROTECTED_BINANCE_PATH:{path}")


def refuse_d2_outcome_request(name: str) -> None:
    raise D2OutcomeRefused(f"D2_OUTCOME_REFUSED:{name}")


def aggregate_1m_to_5m(
    rows: Iterable[tuple[int, float, float, float, float]],
    *,
    end_exclusive_ms: int | None = None,
) -> dict[int, dict[str, Any]]:
    """Deterministic 1m -> 5m aggregation. Does not fabricate missing minutes."""
    by_time = {int(r[0]): r for r in rows}
    if not by_time:
        return {}
    limit = PRE2020_END_EXCLUSIVE if end_exclusive_ms is None else from_ms(int(end_exclusive_ms))
    limit_ms = utc_ms(limit) if end_exclusive_ms is None else int(end_exclusive_ms)
    step = BAR_MS
    start = min(by_time) - (min(by_time) % step)
    end = max(by_time) + 60_000
    out: dict[int, dict[str, Any]] = {}
    bucket = start
    seen: set[int] = set()
    while bucket < end and bucket < limit_ms:
        if bucket in seen:
            raise BitmexSchemaError(f"DUPLICATE_5M_BUCKET:{bucket}")
        members = []
        missing = False
        for k in range(5):
            row = by_time.get(bucket + k * 60_000)
            if row is None:
                missing = True
                break
            members.append(row)
        if not missing:
            highs = [float(m[2]) for m in members]
            lows = [float(m[3]) for m in members]
            if min(lows) > max(highs):
                raise BitmexSchemaError(f"OHLC_INVERSION:{bucket}")
            out[bucket] = {
                "open_time_ms": int(bucket),
                "open": float(members[0][1]),
                "high": max(highs),
                "low": min(lows),
                "close": float(members[-1][4]),
            }
            seen.add(bucket)
        bucket += step
    return out


def _http_get_json(url: str, *, timeout: int = 60, retries: int = 6) -> Any:
    last_err: Exception | None = None
    delay = 1.0
    for _ in range(int(retries)):
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read()
            return json.loads(raw.decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            last_err = exc
            time.sleep(delay)
            delay = min(32.0, delay * 2.0)
    raise RuntimeError(f"BITMEX_HTTP_FAILED:{url}:{last_err}")


def fetch_instrument() -> dict[str, Any]:
    url = f"{BITMEX_INSTRUMENT}?{urllib.parse.urlencode({'symbol': INSTRUMENT, 'count': 1})}"
    payload = _http_get_json(url)
    if not isinstance(payload, list) or not payload:
        raise BitmexSchemaError("INSTRUMENT_EMPTY")
    row = payload[0]
    if str(row.get("symbol")) != INSTRUMENT:
        raise BitmexSchemaError(f"INSTRUMENT_SYMBOL:{row.get('symbol')}")
    return {
        "symbol": row.get("symbol"),
        "typ": row.get("typ"),
        "listing": row.get("listing"),
        "expiry": row.get("expiry"),
        "settle": row.get("settle"),
        "state": row.get("state"),
        "isInverse": row.get("isInverse"),
        "isQuanto": row.get("isQuanto"),
        "quoteCurrency": row.get("quoteCurrency"),
        "underlying": row.get("underlying"),
        "multiplier": row.get("multiplier"),
        "settlCurrency": row.get("settlCurrency"),
        "positionCurrency": row.get("positionCurrency"),
        "referenceSymbol": row.get("referenceSymbol"),
        "tickSize": row.get("tickSize"),
        "lotSize": row.get("lotSize"),
        "source_url": url,
    }


def fetch_bucketed(
    *,
    bin_size: str,
    start_time: datetime,
    count: int = 1000,
    reverse: bool = False,
    end_time: datetime | None = None,
) -> list[dict[str, Any]]:
    params: dict[str, Any] = {
        "binSize": bin_size,
        "partial": "false",
        "symbol": INSTRUMENT,
        "count": int(count),
        "reverse": "true" if reverse else "false",
        "startTime": start_time.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        "columns": "timestamp,symbol,open,high,low,close,trades,volume",
    }
    if end_time is not None:
        params["endTime"] = end_time.strftime("%Y-%m-%dT%H:%M:%S.000Z")
    url = f"{BITMEX_BUCKETED}?{urllib.parse.urlencode(params)}"
    payload = _http_get_json(url)
    if not isinstance(payload, list):
        raise BitmexSchemaError("BUCKETED_NOT_LIST")
    return payload


def parse_5m_page(payload: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    prev_end_ms: int | None = None
    for row in payload:
        if str(row.get("symbol")) != INSTRUMENT:
            raise BitmexSchemaError(f"SYMBOL:{row.get('symbol')}")
        end_ts = parse_bitmex_timestamp(str(row["timestamp"]))
        end_ms = utc_ms(end_ts)
        if prev_end_ms is not None:
            if end_ms == prev_end_ms:
                raise BitmexSchemaError(f"DUPLICATE_TIMESTAMP:{end_ts.isoformat()}")
            if end_ms < prev_end_ms:
                raise BitmexSchemaError(f"NON_MONOTONIC:{end_ts.isoformat()}")
        open_ms = bitmex_end_ts_to_open_ms(end_ts)
        trades = int(row.get("trades") or 0)
        parsed = {
            "source_timestamp": end_ts.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            "open_time_ms": int(open_ms),
            "trades": trades,
            "open": float(row["open"]),
            "high": float(row["high"]),
            "low": float(row["low"]),
            "close": float(row["close"]),
        }
        out.append(parsed)
        prev_end_ms = end_ms
    return out


def theoretical_calendar(*, raw_open_ms: int) -> dict[str, Any]:
    """Maximum legal pre-2020 rows assuming a complete 5m grid after raw_open_ms."""
    first_open = from_ms(int(raw_open_ms))
    # First 00:05 whose RV lookback opens at/after raw_open_ms and whose
    # 288-bar future path ends strictly before 2020-01-01.
    cursor = datetime(first_open.year, first_open.month, first_open.day, 0, 5, tzinfo=UTC)
    if cursor < first_open:
        cursor = cursor + timedelta(days=1)
    first_rv: datetime | None = None
    while cursor < PRE2020_END_EXCLUSIVE:
        if is_pre2020_decision_clock(cursor) and row_timestamp_complete(
            utc_ms(cursor), present_open_ms=None, raw_open_ms=raw_open_ms, assume_complete_grid=True
        ):
            first_rv = cursor
            break
        cursor = cursor + timedelta(days=1)
    if first_rv is None:
        return {
            "RAW_DATA_START": first_open.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            "FIRST_RV_AVAILABLE_T": None,
            "FIRST_RULE_ELIGIBLE_T": None,
            "LAST_RULE_ELIGIBLE_T": None,
            "MAX_PRE2020_ELIGIBLE_DECISION_ROWS": 0,
        }
    complete: list[datetime] = []
    cursor = first_rv
    while cursor < PRE2020_END_EXCLUSIVE:
        if is_pre2020_decision_clock(cursor) and row_timestamp_complete(
            utc_ms(cursor), present_open_ms=None, raw_open_ms=raw_open_ms, assume_complete_grid=True
        ):
            complete.append(cursor)
        cursor = cursor + timedelta(days=1)
    if len(complete) <= RV_TRAILING_WINDOW:
        eligible: list[datetime] = []
    else:
        eligible = complete[RV_TRAILING_WINDOW:]
    return {
        "RAW_DATA_START": first_open.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        "FIRST_RV_AVAILABLE_T": first_rv.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        "FIRST_RULE_ELIGIBLE_T": None
        if not eligible
        else eligible[0].strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        "LAST_RULE_ELIGIBLE_T": None
        if not eligible
        else eligible[-1].strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        "MAX_PRE2020_ELIGIBLE_DECISION_ROWS": int(len(eligible)),
        "COMPLETE_DECISION_ROWS_INCLUDING_WARMUP": int(len(complete)),
        "WARMUP_DECISION_ROWS": int(min(len(complete), RV_TRAILING_WINDOW)),
    }


def row_timestamp_complete(
    t_ms: int,
    *,
    present_open_ms: set[int] | None,
    raw_open_ms: int,
    assume_complete_grid: bool,
) -> bool:
    moment = from_ms(int(t_ms))
    if not is_pre2020_decision_clock(moment):
        return False
    e_ms = int(t_ms) - BAR_MS
    # RV uses bars ending at e_ms - k*BAR_MS, k=288..0 → open = ending - BAR_MS.
    for k in range(RV_RETURN_COUNT, -1, -1):
        open_ms = (e_ms - k * BAR_MS) - BAR_MS
        if open_ms < int(raw_open_ms):
            return False
        last_end = open_ms + BAR_MS
        if last_end > utc_ms(PRE2020_END_EXCLUSIVE):
            return False
        if not assume_complete_grid:
            assert present_open_ms is not None
            if int(open_ms) not in present_open_ms:
                return False
    for k in range(FUTURE_BARS):
        open_ms = int(t_ms) + k * BAR_MS
        bar_end = open_ms + BAR_MS
        if bar_end > utc_ms(PRE2020_END_EXCLUSIVE):
            return False
        if open_ms >= utc_ms(PRE2020_END_EXCLUSIVE):
            return False
        if not assume_complete_grid:
            assert present_open_ms is not None
            if int(open_ms) not in present_open_ms:
                return False
    return True


def count_legal_decision_rows(
    present_open_ms: set[int],
    *,
    raw_open_ms: int,
) -> dict[str, Any]:
    if not present_open_ms:
        raise BitmexSchemaError("NO_PRESENT_BARS")
    first = from_ms(int(raw_open_ms))
    cursor = datetime(first.year, first.month, first.day, 0, 5, tzinfo=UTC)
    if cursor < first:
        cursor = cursor + timedelta(days=1)
    complete: list[datetime] = []
    while cursor < PRE2020_END_EXCLUSIVE:
        if row_timestamp_complete(
            utc_ms(cursor),
            present_open_ms=present_open_ms,
            raw_open_ms=raw_open_ms,
            assume_complete_grid=False,
        ):
            complete.append(cursor)
        cursor = cursor + timedelta(days=1)
    eligible = complete[RV_TRAILING_WINDOW:] if len(complete) > RV_TRAILING_WINDOW else []
    return {
        "RAW_DATA_START": from_ms(int(raw_open_ms)).strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        "FIRST_RV_AVAILABLE_T": None
        if not complete
        else complete[0].strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        "FIRST_RULE_ELIGIBLE_T": None
        if not eligible
        else eligible[0].strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        "LAST_RULE_ELIGIBLE_T": None
        if not eligible
        else eligible[-1].strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        "MAX_PRE2020_ELIGIBLE_DECISION_ROWS": int(len(eligible)),
        "COMPLETE_DECISION_ROWS_INCLUDING_WARMUP": int(len(complete)),
        "WARMUP_DECISION_ROWS": int(min(len(complete), RV_TRAILING_WINDOW)),
        "D2_OUTCOME_COMPUTED_ON_BITMEX": False,
    }


def expected_open_ms_range(raw_open_ms: int, last_open_ms: int) -> list[int]:
    if last_open_ms < raw_open_ms:
        return []
    if raw_open_ms % BAR_MS != 0 or last_open_ms % BAR_MS != 0:
        raise BitmexSchemaError("RANGE_NOT_5M_ALIGNED")
    n = ((last_open_ms - raw_open_ms) // BAR_MS) + 1
    return [int(raw_open_ms + i * BAR_MS) for i in range(int(n))]


def census_gaps(present_open_ms: set[int], *, raw_open_ms: int, last_open_ms: int) -> dict[str, Any]:
    expected = expected_open_ms_range(raw_open_ms, last_open_ms)
    present = set(int(x) for x in present_open_ms)
    missing = [ms for ms in expected if ms not in present]
    extra = sorted(ms for ms in present if ms < raw_open_ms or ms > last_open_ms)
    if extra:
        raise BitmexSchemaError(f"EXTRA_OUT_OF_RANGE:{len(extra)}")
    missing_iso = [from_ms(ms).strftime("%Y-%m-%dT%H:%M:%S.000Z") for ms in missing]
    return {
        "expected_5m_bars": int(len(expected)),
        "observed_5m_bars": int(len(present)),
        "missing_bucket_count": int(len(missing)),
        "missing_open_timestamps_head": missing_iso[:25],
        "missing_open_timestamps_tail": missing_iso[-25:] if len(missing_iso) > 25 else [],
        "missing_open_timestamps_sha256": sha256_bytes(
            ("\n".join(missing_iso) + ("\n" if missing_iso else "")).encode("utf-8")
        ),
        "duplicates_silently_accepted": False,
        "missing_silently_accepted": False,
    }


def acquire_pre2020_5m(*, repo: Path, sleep_s: float = 0.35) -> dict[str, Any]:
    """Download official 5m buckets through the 2020-01-01 exclusive boundary.

    Stores raw page bytes and a canonical JSONL.gz. Does not compute D2 outcomes.
    """
    base = repo
    out_dir = base / ARTIFACT_REL
    raw_dir = out_dir / "raw_pages"
    raw_dir.mkdir(parents=True, exist_ok=True)
    start = LISTING_UTC
    end_exclusive = PRE2020_END_EXCLUSIVE
    cursor = start
    pages: list[dict[str, Any]] = []
    canonical_rows: list[dict[str, Any]] = []
    seen_open: set[int] = set()
    page_i = 0
    retrieval_start = datetime.now(tz=UTC)
    while cursor <= end_exclusive + timedelta(minutes=5):
        payload = fetch_bucketed(
            bin_size="5m",
            start_time=cursor,
            count=1000,
            reverse=False,
            end_time=end_exclusive + timedelta(minutes=5),
        )
        raw = json.dumps(payload, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
        page_i += 1
        page_path = raw_dir / f"page-{page_i:04d}.json"
        page_path.write_bytes(raw)
        pages.append(
            {
                "page": page_i,
                "n": len(payload),
                "sha256": sha256_bytes(raw),
                "startTime": cursor.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            }
        )
        print(
            f"bitmex_5m_page={page_i} n={len(payload)} start={cursor.isoformat()}",
            flush=True,
        )
        if not payload:
            break
        parsed = parse_5m_page(payload)
        stop = False
        for row in parsed:
            open_ms = int(row["open_time_ms"])
            if open_ms in seen_open:
                raise BitmexSchemaError(f"DUPLICATE_OPEN:{open_ms}")
            if open_ms >= utc_ms(end_exclusive):
                stop = True
                continue
            seen_open.add(open_ms)
            canonical_rows.append(row)
        last_end = parse_bitmex_timestamp(str(payload[-1]["timestamp"]))
        # startTime is inclusive and second-resolution; advance by one 5m bin.
        next_cursor = last_end + timedelta(milliseconds=BAR_MS)
        if next_cursor <= cursor:
            raise BitmexSchemaError("PAGINATION_STALLED")
        cursor = next_cursor
        if stop or last_end >= end_exclusive:
            break
        time.sleep(float(sleep_s))
    retrieval_end = datetime.now(tz=UTC)
    canonical_rows.sort(key=lambda r: int(r["open_time_ms"]))
    # Re-check monotonic unique
    prev = None
    for row in canonical_rows:
        cur = int(row["open_time_ms"])
        if prev is not None and cur <= prev:
            raise BitmexSchemaError(f"CANONICAL_NON_MONOTONIC:{cur}")
        prev = cur
    jsonl = "\n".join(json.dumps(r, separators=(",", ":"), sort_keys=True) for r in canonical_rows)
    if canonical_rows:
        jsonl += "\n"
    jsonl_bytes = jsonl.encode("utf-8")
    gz_path = out_dir / "canonical_5m.jsonl.gz"
    gz_bytes = gzip.compress(jsonl_bytes, compresslevel=9, mtime=0)
    gz_path.write_bytes(gz_bytes)
    raw_open_ms = int(canonical_rows[0]["open_time_ms"]) if canonical_rows else utc_ms(LISTING_UTC)
    last_open_ms = int(canonical_rows[-1]["open_time_ms"]) if canonical_rows else raw_open_ms
    present = {int(r["open_time_ms"]) for r in canonical_rows}
    zero_trade = sum(1 for r in canonical_rows if int(r["trades"]) == 0)
    # Zero-trade buckets remain present timestamps; they are not silently dropped.
    gaps = census_gaps(present, raw_open_ms=raw_open_ms, last_open_ms=last_open_ms)
    legal = count_legal_decision_rows(present, raw_open_ms=raw_open_ms)
    theoretical = theoretical_calendar(raw_open_ms=raw_open_ms)
    instrument = fetch_instrument()
    authority = {
        "schema": "signalbot_d2_bitmex_pre2020_source_authority",
        "parser_version": PARSER_VERSION,
        "instrument": INSTRUMENT,
        "instrument_typ": INSTRUMENT_TYP,
        "source_identity": {
            "primary": "BitMEX REST GET /api/v1/trade/bucketed binSize=5m symbol=XBTUSD partial=false",
            "endpoint": BITMEX_BUCKETED,
            "docs": BITMEX_BUCKETED_DOCS,
            "launch_post": BITMEX_LAUNCH_POST,
            "candle_support": BITMEX_CANDLE_SUPPORT,
            "public_archive": BITMEX_PUBLIC_ARCHIVE,
            "timestamp_semantics": TIMESTAMP_SEMANTICS,
            "ohlc_schema": ["timestamp", "symbol", "open", "high", "low", "close", "trades", "volume"],
            "third_party_kaggle_used": False,
        },
        "instrument_metadata": instrument,
        "retrieval_start_utc": retrieval_start.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        "retrieval_end_utc": retrieval_end.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        "raw_page_count": int(len(pages)),
        "raw_page_hashes": pages,
        "raw_pages_concat_sha256": sha256_bytes(
            "".join(p["sha256"] for p in pages).encode("ascii")
        ),
        "canonical_jsonl_sha256": sha256_bytes(jsonl_bytes),
        "canonical_jsonl_gz_sha256": sha256_bytes(gz_bytes),
        "canonical_relative_path": str(gz_path.relative_to(base)),
        "coverage": {
            "first_open_time": from_ms(raw_open_ms).strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            "last_open_time": from_ms(last_open_ms).strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            "observed_5m_bars": int(len(canonical_rows)),
            "zero_trade_bucket_count": int(zero_trade),
            "pre2020_end_exclusive": PRE2020_END_EXCLUSIVE.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        },
        "gaps": gaps,
        "calendar_theoretical_complete_grid": theoretical,
        "calendar_observed_timestamp_presence": legal,
        "scientific_outcomes": {
            "D2_OUTCOME_COMPUTED_ON_BITMEX": False,
            "MU_RULE": None,
            "DELTA": None,
            "candidate_severity_difference": None,
            "randomization_p_value": None,
            "confirmation_classification": None,
        },
        "contains_human_readable_price_dump": False,
        "parser_version_note": "open_time_ms = official bucket-end timestamp minus 5 minutes",
    }
    auth_path = base / AUTHORITY_REL
    auth_path.parent.mkdir(parents=True, exist_ok=True)
    serializable = json.loads(json.dumps(authority, sort_keys=True, default=str))
    auth_path.write_text(json.dumps(serializable, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return serializable


if __name__ == "__main__":
    from scripts.research.discovery_sprint_01 import common as C

    payload = acquire_pre2020_5m(repo=C.repo_root())
    summary = {
        "instrument": payload["instrument"],
        "raw_page_count": payload["raw_page_count"],
        "observed_5m_bars": payload["coverage"]["observed_5m_bars"],
        "missing_bucket_count": payload["gaps"]["missing_bucket_count"],
        "calendar_theoretical": payload["calendar_theoretical_complete_grid"],
        "calendar_observed": payload["calendar_observed_timestamp_presence"],
        "D2_OUTCOME_COMPUTED_ON_BITMEX": payload["scientific_outcomes"][
            "D2_OUTCOME_COMPUTED_ON_BITMEX"
        ],
        "canonical_jsonl_sha256": payload["canonical_jsonl_sha256"],
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
