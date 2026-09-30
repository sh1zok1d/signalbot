"""D7_BITMEX_ACTIVITY_V0 — outcome-blind activity pin for pre-2020 XBTUSD.

Official BitMEX trade/bucketed 5m only. Preserves quote-activity fields.
Does not compute IMPACT_PROXY, the D7 state, or NEXT_HOUR_HIGH_IMPACT_STATE.
Does not modify the pinned D2 BitMEX dataset. Does not open Binance 2025/2026.
"""
from __future__ import annotations

import gzip
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping

from scripts.research.d2_bitmex_pre2020 import (
    BAR_MS,
    bitmex_end_ts_to_open_ms,
    parse_bitmex_timestamp,
    sha256_bytes,
    utc_ms,
)

UTC = timezone.utc
DATASET_ID = "D7_BITMEX_ACTIVITY_V0"
PARSER_VERSION = "D7_BITMEX_ACTIVITY_PARSER_V0"
INSTRUMENT = "XBTUSD"
LISTING_UTC = datetime(2016, 5, 13, 12, 0, tzinfo=UTC)
PRE2020_END_EXCLUSIVE = datetime(2020, 1, 1, 0, 0, tzinfo=UTC)
BITMEX_BUCKETED = "https://www.bitmex.com/api/v1/trade/bucketed"
USER_AGENT = "signalbot-d7-bitmex-activity-v0/1.0"
OUT_REL = Path("docs/research_data") / DATASET_ID
D2_CANONICAL_REL = Path("docs/research_data/D2_BITMEX_PRE2020_XBTUSD/canonical_5m.jsonl.gz")
ACTIVITY_FIELDS = (
    "volume",
    "foreignNotional",
    "homeNotional",
    "turnover",
    "trades",
    "vwap",
    "lastSize",
)
OHLC_FIELDS = ("open", "high", "low", "close")
CANONICAL_FIELDS = (
    "source_timestamp",
    "open_time_ms",
    "symbol",
    "pool",
    *OHLC_FIELDS,
    *ACTIVITY_FIELDS,
)


class ActivitySchemaError(RuntimeError):
    pass


def refuse_protected_or_d2_write(path: Path) -> None:
    text = str(path).replace("\\", "/")
    if "D2_BITMEX_PRE2020" in text:
        raise ActivitySchemaError(f"D2_DATASET_IMMUTABLE:{path}")
    if "2025-" in text or "2026-" in text:
        raise ActivitySchemaError(f"PROTECTED_BINANCE_PATH:{path}")


def _request_url(start: datetime) -> str:
    params = {
        "binSize": "5m",
        "partial": "false",
        "symbol": INSTRUMENT,
        "count": "1000",
        "reverse": "false",
        "startTime": start.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        "endTime": (PRE2020_END_EXCLUSIVE + timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%S.000Z"),
    }
    return f"{BITMEX_BUCKETED}?{urllib.parse.urlencode(params)}"


def fetch_raw(url: str, *, timeout: int = 60, retries: int = 8) -> bytes:
    delay = 1.0
    last: Exception | None = None
    for _ in range(int(retries)):
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read()
        except urllib.error.HTTPError as exc:
            last = exc
            if exc.code == 429:
                time.sleep(max(delay, 5.0))
            else:
                time.sleep(delay)
            delay = min(30.0, delay * 2.0)
        except (urllib.error.URLError, TimeoutError) as exc:
            last = exc
            time.sleep(delay)
            delay = min(30.0, delay * 2.0)
    raise ActivitySchemaError(f"BITMEX_HTTP_FAILED:{last}")


def parse_activity_page(payload: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep official activity fields. Missing keys stay null. No fill."""
    if not isinstance(payload, list):
        raise ActivitySchemaError("PAGE_NOT_LIST")
    out: list[dict[str, Any]] = []
    prev_end: int | None = None
    for row in payload:
        if str(row.get("symbol")) != INSTRUMENT:
            raise ActivitySchemaError(f"SYMBOL:{row.get('symbol')}")
        if "timestamp" not in row:
            raise ActivitySchemaError("TIMESTAMP_MISSING")
        end_ts = parse_bitmex_timestamp(str(row["timestamp"]))
        end_ms = utc_ms(end_ts)
        if prev_end is not None:
            if end_ms == prev_end:
                raise ActivitySchemaError(f"DUPLICATE_TIMESTAMP:{end_ts.isoformat()}")
            if end_ms < prev_end:
                raise ActivitySchemaError(f"NON_MONOTONIC:{end_ts.isoformat()}")
        parsed: dict[str, Any] = {
            "source_timestamp": end_ts.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            "open_time_ms": int(bitmex_end_ts_to_open_ms(end_ts)),
            "symbol": INSTRUMENT,
            "pool": row.get("pool"),
        }
        for key in OHLC_FIELDS:
            if row.get(key) is None:
                raise ActivitySchemaError(f"OHLC_NULL:{key}:{parsed['source_timestamp']}")
            parsed[key] = row[key]
        for key in ACTIVITY_FIELDS:
            parsed[key] = row.get(key)
        out.append(parsed)
        prev_end = end_ms
    return out


def _load_manifest(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def acquire(*, repo: Path, sleep_s: float = 0.25) -> dict[str, Any]:
    out_dir = repo / OUT_REL
    refuse_protected_or_d2_write(out_dir)
    raw_dir = out_dir / "raw_pages"
    raw_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = out_dir / "raw_manifest.jsonl"
    pages = _load_manifest(manifest_path)
    if pages:
        cursor = parse_bitmex_timestamp(pages[-1]["next_startTime"])
        page_i = int(pages[-1]["page"])
    else:
        cursor = LISTING_UTC
        page_i = 0
    retrieval_start = datetime.now(tz=UTC)
    end_ms = utc_ms(PRE2020_END_EXCLUSIVE)
    while cursor < PRE2020_END_EXCLUSIVE + timedelta(minutes=5):
        url = _request_url(cursor)
        raw = fetch_raw(url)
        page_i += 1
        page_path = raw_dir / f"page-{page_i:04d}.json"
        refuse_protected_or_d2_write(page_path)
        page_path.write_bytes(raw)
        payload = json.loads(raw.decode("utf-8"))
        if not isinstance(payload, list):
            raise ActivitySchemaError("PAGE_NOT_LIST")
        parsed = parse_activity_page(payload) if payload else []
        kept = [row for row in parsed if int(row["open_time_ms"]) < end_ms]
        if payload:
            last_end = parse_bitmex_timestamp(str(payload[-1]["timestamp"]))
            next_cursor = last_end + timedelta(milliseconds=BAR_MS)
        else:
            next_cursor = cursor
        record = {
            "page": page_i,
            "n": len(payload),
            "n_kept": len(kept),
            "sha256": sha256_bytes(raw),
            "request_url": url,
            "startTime": cursor.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            "next_startTime": next_cursor.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            "bytes": len(raw),
        }
        with manifest_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, sort_keys=True) + "\n")
        pages.append(record)
        print(f"d7_bitmex_page={page_i} n={len(payload)} start={record['startTime']}", flush=True)
        if not payload or next_cursor <= cursor or last_end >= PRE2020_END_EXCLUSIVE:
            break
        cursor = next_cursor
        time.sleep(float(sleep_s))
    return write_canonical(repo, pages, retrieval_start=retrieval_start)


def write_canonical(repo: Path, pages: list[dict[str, Any]], *, retrieval_start: datetime) -> dict[str, Any]:
    out_dir = repo / OUT_REL
    raw_dir = out_dir / "raw_pages"
    rows: list[dict[str, Any]] = []
    seen: set[int] = set()
    end_ms = utc_ms(PRE2020_END_EXCLUSIVE)
    for page in pages:
        raw = (raw_dir / f"page-{int(page['page']):04d}.json").read_bytes()
        if sha256_bytes(raw) != page["sha256"]:
            raise ActivitySchemaError(f"RAW_HASH_MISMATCH:{page['page']}")
        payload = json.loads(raw.decode("utf-8"))
        for row in parse_activity_page(payload):
            open_ms = int(row["open_time_ms"])
            if open_ms >= end_ms:
                continue
            if open_ms in seen:
                raise ActivitySchemaError(f"DUPLICATE_OPEN:{open_ms}")
            seen.add(open_ms)
            rows.append(row)
    rows.sort(key=lambda r: int(r["open_time_ms"]))
    prev = None
    for row in rows:
        cur = int(row["open_time_ms"])
        if prev is not None and cur <= prev:
            raise ActivitySchemaError(f"CANONICAL_NON_MONOTONIC:{cur}")
        prev = cur
    jsonl = "".join(
        json.dumps({k: row.get(k) for k in CANONICAL_FIELDS}, separators=(",", ":"), sort_keys=True) + "\n"
        for row in rows
    )
    jsonl_bytes = jsonl.encode("utf-8")
    gz_bytes = gzip.compress(jsonl_bytes, compresslevel=9, mtime=0)
    gz_path = out_dir / "canonical_5m.jsonl.gz"
    refuse_protected_or_d2_write(gz_path)
    gz_path.write_bytes(gz_bytes)
    quality = audit_rows(rows)
    authority = {
        "schema": "signalbot_d7_bitmex_activity_v0_source_authority",
        "dataset_id": DATASET_ID,
        "parser_version": PARSER_VERSION,
        "instrument": INSTRUMENT,
        "source": {
            "endpoint": BITMEX_BUCKETED,
            "docs": "https://docs.bitmex.com/api-explorer/get-trade-bucketed",
            "binSize": "5m",
            "partial": False,
            "symbol": INSTRUMENT,
            "count": 1000,
            "reverse": False,
            "columns_parameter": None,
            "timestamp_semantics": "BUCKET_END",
            "open_time_rule": "open_time_ms = official bucket-end timestamp minus 5 minutes",
            "third_party_kaggle_used": False,
            "d2_canonical_modified": False,
        },
        "interval": {
            "request_start": LISTING_UTC.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            "end_exclusive": PRE2020_END_EXCLUSIVE.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            "first_open_time": _open_iso(rows[0]["open_time_ms"]) if rows else None,
            "last_open_time": _open_iso(rows[-1]["open_time_ms"]) if rows else None,
        },
        "row_count": len(rows),
        "raw_page_count": len(pages),
        "raw_pages_concat_sha256": sha256_bytes("".join(p["sha256"] for p in pages).encode("ascii")),
        "canonical_jsonl_sha256": sha256_bytes(jsonl_bytes),
        "canonical_jsonl_gz_sha256": sha256_bytes(gz_bytes),
        "canonical_relative_path": str(gz_path.relative_to(repo)),
        "raw_manifest_sha256": sha256_bytes((out_dir / "raw_manifest.jsonl").read_bytes()),
        "retrieval_start_utc": retrieval_start.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        "retrieval_end_utc": datetime.now(tz=UTC).strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        "quality": quality,
        "scientific_outcomes": {
            "D7_PRIMARY_TARGET_OPENED": False,
            "D7_EFFECT_COMPUTED": False,
            "NEXT_HOUR_HIGH_IMPACT_STATE_COMPUTED": False,
            "BINANCE_2025_OPENED": False,
            "BINANCE_2026_OPENED": False,
        },
    }
    # first_open uses open_time, not the bucket-end source timestamp
    if rows:
        authority["interval"]["first_open_time"] = _open_iso(rows[0]["open_time_ms"])
        authority["interval"]["first_bucket_end"] = rows[0]["source_timestamp"]
        authority["interval"]["last_bucket_end"] = rows[-1]["source_timestamp"]
    auth_path = out_dir / "SOURCE_AUTHORITY.json"
    refuse_protected_or_d2_write(auth_path)
    auth_path.write_text(json.dumps(authority, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    d2_path = repo / D2_CANONICAL_REL
    if d2_path.exists():
        authority["d2_canonical_sha256_unchanged_bytes"] = sha256_bytes(d2_path.read_bytes())
        auth_path.write_text(json.dumps(authority, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return authority


def _open_iso(open_ms: int) -> str:
    return datetime.fromtimestamp(int(open_ms) / 1000.0, tz=UTC).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def _num(value: Any) -> float | None:
    if value is None:
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out


def audit_rows(rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    """Coverage and unit-identity only. No return, no state, no t+1 target."""
    opens = [int(r["open_time_ms"]) for r in rows]
    duplicates = len(opens) - len(set(opens))
    non_mono = sum(1 for a, b in zip(opens, opens[1:]) if b <= a)
    gaps = []
    for a, b in zip(opens, opens[1:]):
        if b - a != BAR_MS:
            gaps.append({"from_open_ms": a, "to_open_ms": b, "missing_bars": (b - a) // BAR_MS - 1})
    hour_ms = 3_600_000
    from collections import Counter
    by_hour = Counter(ms // hour_ms for ms in opens)
    incomplete = sorted((h, c) for h, c in by_hour.items() if c != 12)
    nulls = {key: sum(1 for r in rows if r.get(key) is None) for key in CANONICAL_FIELDS}
    zero_volume = sum(1 for r in rows if _num(r.get("volume")) == 0.0)
    zero_foreign = sum(1 for r in rows if _num(r.get("foreignNotional")) == 0.0)
    zero_trades = sum(1 for r in rows if _num(r.get("trades")) == 0.0)
    both_zero = sum(
        1 for r in rows if _num(r.get("volume")) == 0.0 and _num(r.get("foreignNotional")) == 0.0
    )
    ne = 0
    max_abs = 0.0
    checked = 0
    for row in rows:
        vol = _num(row.get("volume"))
        foreign = _num(row.get("foreignNotional"))
        if vol is None or foreign is None:
            continue
        checked += 1
        diff = abs(foreign - vol)
        if diff > 1e-6:
            ne += 1
            if diff > max_abs:
                max_abs = diff
    return {
        "row_count": len(rows),
        "duplicate_timestamps": duplicates,
        "non_monotonic_steps": non_mono,
        "missing_bucket_events": len(gaps),
        "missing_buckets": int(sum(g["missing_bars"] for g in gaps)),
        "gap_spans": [
            {
                "from_open": _open_iso(g["from_open_ms"]),
                "to_open": _open_iso(g["to_open_ms"]),
                "missing_bars": g["missing_bars"],
            }
            for g in gaps[:5]
        ],
        "utc_hours_touched": len(by_hour),
        "complete_utc_hours": sum(1 for c in by_hour.values() if c == 12),
        "incomplete_utc_hours": len(incomplete),
        "incomplete_hours": [
            {"hour_start": _open_iso(h * hour_ms), "bars": c} for h, c in incomplete[:8]
        ],
        "zero_volume_buckets": zero_volume,
        "zero_foreign_notional_buckets": zero_foreign,
        "zero_trades_buckets": zero_trades,
        "zero_volume_and_foreign_notional": both_zero,
        "null_counts": nulls,
        "volume_foreign_notional_rows_compared": checked,
        "volume_ne_foreign_notional": ne,
        "volume_foreign_max_abs_diff": max_abs,
        "no_fill": True,
        "d7_target_computed": False,
    }


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def main() -> None:
    payload = acquire(repo=repo_root())
    summary = {
        "dataset_id": payload["dataset_id"],
        "row_count": payload["row_count"],
        "canonical_jsonl_gz_sha256": payload["canonical_jsonl_gz_sha256"],
        "quality": payload["quality"],
        "D7_PRIMARY_TARGET_OPENED": False,
    }
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
