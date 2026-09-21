"""Outcome-blind MARKET-06 source-route materializer.

Binance USD-M BTCUSDT perpetual 5m trade-price klines (Vision archive)
+ OKX BTC-USDT spot 5m history-candles, 2022-01-01 .. 2024-12-31.

Inspects timestamps, schema, checksums, coverage only.
Does not compute dislocation, spread, returns, MAE, or any price-derived
relationship. Does not print OHLC.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from calendar import monthrange
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
ARTIFACT_ROOT = REPO / "artifacts" / "research_data" / "MARKET_06_OKX_BINANCE_FEASIBILITY_V0"
DOCS_ROOT = REPO / "docs" / "research_data" / "MARKET_06_OKX_BINANCE_FEASIBILITY_V0"

WINDOW_START_MS = int(datetime(2022, 1, 1, tzinfo=timezone.utc).timestamp() * 1000)
WINDOW_END_EXCLUSIVE_MS = int(datetime(2025, 1, 1, tzinfo=timezone.utc).timestamp() * 1000)
BAR_MS = 300_000
UA = {"User-Agent": "signalbot-market06-okx-binance-feasibility"}
OKX_HISTORY = "https://www.okx.com/api/v5/market/history-candles"
BINANCE_ZIP = (
    "https://data.binance.vision/data/futures/um/monthly/klines/BTCUSDT/5m/"
    "BTCUSDT-5m-{period}.zip"
)
BINANCE_CHECKSUM = BINANCE_ZIP + ".CHECKSUM"
MONTHS = [f"{y}-{m:02d}" for y in (2022, 2023, 2024) for m in range(1, 13)]
FORBIDDEN_REPORT_KEYS = frozenset(
    {
        "open",
        "high",
        "low",
        "close",
        "ohlc",
        "dislocation",
        "spread",
        "zscore",
        "z-score",
        "future_return",
        "mae",
        "beta",
        "correlation",
        "prediction",
        "drawdown",
    }
)


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def ms_to_utc(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def assert_no_forbidden(payload: Any, *, where: str) -> None:
    if isinstance(payload, dict):
        keys = {str(k).lower() for k in payload}
        hit = keys & FORBIDDEN_REPORT_KEYS
        if hit:
            raise RuntimeError(f"SCIENTIFIC_OR_PRICE_FIELD_FORBIDDEN:{where}:{sorted(hit)}")
        for k, v in payload.items():
            assert_no_forbidden(v, where=f"{where}.{k}")
    elif isinstance(payload, list):
        for i, item in enumerate(payload):
            assert_no_forbidden(item, where=f"{where}[{i}]")


def http_get(url: str, *, timeout: float = 60.0, retries: int = 6) -> tuple[int, bytes, dict[str, str]]:
    delay = 0.5
    last_exc: Exception | None = None
    for attempt in range(retries):
        req = urllib.request.Request(url, headers=UA)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = resp.read()
                headers = {k: v for k, v in resp.headers.items()}
                return int(resp.status), body, headers
        except urllib.error.HTTPError as exc:
            body = exc.read() if hasattr(exc, "read") else b""
            if exc.code in {429, 500, 502, 503, 504} and attempt + 1 < retries:
                time.sleep(delay)
                delay = min(delay * 2, 16)
                last_exc = exc
                continue
            return int(exc.code), body, dict(exc.headers.items()) if exc.headers else {}
        except Exception as exc:  # noqa: BLE001 — resume/retry network
            last_exc = exc
            if attempt + 1 < retries:
                time.sleep(delay)
                delay = min(delay * 2, 16)
                continue
            raise
    raise RuntimeError(f"HTTP_GET_FAILED:{url}:{last_exc}")


def parse_checksum_sidecar(text: str, expected_name: str) -> str:
    line = text.strip().splitlines()[0].strip()
    match = re.match(r"^([0-9a-fA-F]{64})\s+\*?(\S+)$", line)
    if not match:
        raise RuntimeError(f"CHECKSUM_SIDECAR_UNPARSEABLE:{expected_name}")
    digest, name = match.group(1).lower(), match.group(2)
    if name != expected_name:
        raise RuntimeError(f"CHECKSUM_FILENAME_MISMATCH:{name}:{expected_name}")
    return digest


def expected_open_times_for_month(period: str) -> list[int]:
    year, month = (int(x) for x in period.split("-"))
    start = datetime(year, month, 1, tzinfo=timezone.utc)
    last_day = monthrange(year, month)[1]
    end = datetime(year, month, last_day, 23, 55, tzinfo=timezone.utc)
    start_ms = int(start.timestamp() * 1000)
    end_ms = int(end.timestamp() * 1000)
    out = []
    t = start_ms
    while t <= end_ms:
        out.append(t)
        t += BAR_MS
    return out


def download_binance(raw_dir: Path) -> list[dict[str, Any]]:
    raw_dir.mkdir(parents=True, exist_ok=True)
    ledger: list[dict[str, Any]] = []
    for period in MONTHS:
        zip_name = f"BTCUSDT-5m-{period}.zip"
        zip_path = raw_dir / zip_name
        checksum_path = raw_dir / f"{zip_name}.CHECKSUM"
        zip_url = BINANCE_ZIP.format(period=period)
        checksum_url = BINANCE_CHECKSUM.format(period=period)
        print(f"BINANCE {period}", flush=True)
        cs_status, cs_body, _ = http_get(checksum_url)
        if cs_status != 200:
            raise RuntimeError(f"BINANCE_CHECKSUM_HTTP:{period}:{cs_status}")
        checksum_path.write_bytes(cs_body)
        expected_sha = parse_checksum_sidecar(cs_body.decode("utf-8"), zip_name)
        if zip_path.is_file() and sha256_bytes(zip_path.read_bytes()) == expected_sha:
            zip_bytes = zip_path.read_bytes()
            zip_status = 200
        else:
            zip_status, zip_bytes, _ = http_get(zip_url, timeout=120)
            if zip_status != 200:
                raise RuntimeError(f"BINANCE_ZIP_HTTP:{period}:{zip_status}")
            zip_path.write_bytes(zip_bytes)
        local_sha = sha256_bytes(zip_bytes)
        if local_sha != expected_sha:
            raise RuntimeError(f"BINANCE_CHECKSUM_MISMATCH:{period}")
        open_times: list[int] = []
        member_names: list[str] = []
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            member_names = zf.namelist()
            csv_members = [n for n in member_names if n.lower().endswith(".csv")]
            if len(csv_members) != 1:
                raise RuntimeError(f"BINANCE_CSV_MEMBER_COUNT:{period}:{member_names}")
            with zf.open(csv_members[0]) as handle:
                reader = csv.reader(io.TextIOWrapper(handle, encoding="utf-8", newline=""))
                for row in reader:
                    if not row:
                        continue
                    if row[0].lower() in {"open_time", "open time"}:
                        continue
                    ts = int(row[0])
                    if WINDOW_START_MS <= ts < WINDOW_END_EXCLUSIVE_MS:
                        open_times.append(ts)
        unique = sorted(set(open_times))
        expected = [
            t
            for t in expected_open_times_for_month(period)
            if WINDOW_START_MS <= t < WINDOW_END_EXCLUSIVE_MS
        ]
        missing = [t for t in expected if t not in set(unique)]
        extra = [t for t in unique if t not in set(expected)]
        dupes = len(open_times) - len(unique)
        rec = {
            "period": period,
            "source_url": zip_url,
            "checksum_url": checksum_url,
            "http_status_zip": zip_status,
            "http_status_checksum": cs_status,
            "byte_size": len(zip_bytes),
            "local_sha256": local_sha,
            "expected_sha256": expected_sha,
            "checksum_verification": "VERIFIED",
            "zip_member_names": member_names,
            "row_count": len(open_times),
            "unique_open_times": len(unique),
            "duplicate_count": dupes,
            "first_open_time_ms": unique[0] if unique else None,
            "last_open_time_ms": unique[-1] if unique else None,
            "first_open_time_utc": ms_to_utc(unique[0]) if unique else None,
            "last_open_time_utc": ms_to_utc(unique[-1]) if unique else None,
            "expected_rows_in_month_window": len(expected),
            "missing_count": len(missing),
            "extra_count": len(extra),
            "all_5m_aligned": all(t % BAR_MS == 0 for t in unique),
        }
        assert_no_forbidden(rec, where=f"binance.{period}")
        ledger.append(rec)
    return ledger


def download_okx(raw_dir: Path, delay_s: float = 0.13) -> list[dict[str, Any]]:
    raw_dir.mkdir(parents=True, exist_ok=True)
    pages: list[dict[str, Any]] = []
    after = WINDOW_END_EXCLUSIVE_MS
    page_index = 0
    seen_oldest: set[int] = set()
    while True:
        page_index += 1
        params = {
            "instId": "BTC-USDT",
            "bar": "5m",
            "after": str(after),
            "limit": "300",
        }
        url = OKX_HISTORY + "?" + urllib.parse.urlencode(params)
        retrieval_utc = utc_now()
        status, body, _headers = http_get(url)
        payload_sha = sha256_bytes(body)
        page_path = raw_dir / f"page-{page_index:06d}.json"
        page_path.write_bytes(body)
        if status != 200:
            raise RuntimeError(f"OKX_HTTP:{page_index}:{status}")
        parsed = json.loads(body.decode("utf-8"))
        if str(parsed.get("code")) != "0":
            raise RuntimeError(f"OKX_CODE:{page_index}:{parsed.get('code')}:{parsed.get('msg')}")
        rows = parsed.get("data") or []
        if not isinstance(rows, list) or not rows:
            rec = {
                "page_index": page_index,
                "request": params,
                "url": url,
                "retrieval_utc": retrieval_utc,
                "http_status": status,
                "okx_code": parsed.get("code"),
                "payload_sha256": payload_sha,
                "byte_size": len(body),
                "path": str(page_path.relative_to(ARTIFACT_ROOT)),
                "n_records": 0,
                "n_completed": 0,
                "n_in_window": 0,
                "first_ts_ms": None,
                "last_ts_ms": None,
                "stop_reason": "EMPTY_PAGE",
            }
            pages.append(rec)
            break
        ts_list: list[int] = []
        confirm_values: set[str] = set()
        n_fields: set[int] = set()
        n_completed = 0
        n_in_window = 0
        for row in rows:
            if not isinstance(row, list):
                raise RuntimeError(f"OKX_ROW_NOT_ARRAY:{page_index}")
            n_fields.add(len(row))
            ts = int(row[0])
            confirm = str(row[8]) if len(row) > 8 else ""
            confirm_values.add(confirm)
            ts_list.append(ts)
            if confirm == "1":
                n_completed += 1
            if WINDOW_START_MS <= ts < WINDOW_END_EXCLUSIVE_MS:
                n_in_window += 1
        newest, oldest = ts_list[0], ts_list[-1]
        rec = {
            "page_index": page_index,
            "request": params,
            "url": url,
            "retrieval_utc": retrieval_utc,
            "http_status": status,
            "okx_code": parsed.get("code"),
            "payload_sha256": payload_sha,
            "byte_size": len(body),
            "path": str(page_path.relative_to(ARTIFACT_ROOT)),
            "n_records": len(rows),
            "n_completed": n_completed,
            "n_in_window": n_in_window,
            "n_fields": sorted(n_fields),
            "confirm_values": sorted(confirm_values),
            "all_confirm_1": confirm_values == {"1"},
            "all_5m_aligned": all(t % BAR_MS == 0 for t in ts_list),
            "newest_ts_ms": newest,
            "oldest_ts_ms": oldest,
            "newest_ts_utc": ms_to_utc(newest),
            "oldest_ts_utc": ms_to_utc(oldest),
            "first_ts_ms": newest,
            "last_ts_ms": oldest,
        }
        assert_no_forbidden(rec, where=f"okx.page{page_index}")
        pages.append(rec)
        print(
            f"OKX page {page_index} n={len(rows)} newest={rec['newest_ts_utc']} oldest={rec['oldest_ts_utc']}",
            flush=True,
        )
        if oldest in seen_oldest:
            raise RuntimeError(f"OKX_PAGINATION_STUCK:{oldest}")
        seen_oldest.add(oldest)
        if oldest < WINDOW_START_MS:
            rec["stop_reason"] = "CROSSED_WINDOW_START"
            break
        after = oldest
        time.sleep(delay_s)
    return pages


def longest_gap_bars(sorted_unique: list[int]) -> int:
    longest = 0
    for prev, cur in zip(sorted_unique, sorted_unique[1:]):
        delta = (cur - prev) // BAR_MS - 1
        if delta > longest:
            longest = delta
    return longest


def census(binance_times: list[int], okx_times: list[int]) -> dict[str, Any]:
    expected = list(range(WINDOW_START_MS, WINDOW_END_EXCLUSIVE_MS, BAR_MS))
    b_all = binance_times
    o_all = okx_times
    b_unique = sorted(set(b_all))
    o_unique = sorted(set(o_all))
    b_set, o_set, e_set = set(b_unique), set(o_unique), set(expected)
    aligned = sorted(b_set & o_set)
    report = {
        "window_start_utc": "2022-01-01T00:00:00Z",
        "window_end_exclusive_utc": "2025-01-01T00:00:00Z",
        "expected_5m_bars": len(expected),
        "BINANCE_ROWS": len(b_all),
        "OKX_ROWS": len(o_all),
        "BINANCE_UNIQUE_TIMESTAMPS": len(b_unique),
        "OKX_UNIQUE_TIMESTAMPS": len(o_unique),
        "BINANCE_DUPLICATES": len(b_all) - len(b_unique),
        "OKX_DUPLICATES": len(o_all) - len(o_unique),
        "BINANCE_MISSING_TIMESTAMPS": len(e_set - b_set),
        "OKX_MISSING_TIMESTAMPS": len(e_set - o_set),
        "BINANCE_LONGEST_GAP_BARS": longest_gap_bars(b_unique),
        "OKX_LONGEST_GAP_BARS": longest_gap_bars(o_unique),
        "ALIGNED_TIMESTAMPS": len(aligned),
        "BINANCE_ONLY_TIMESTAMPS": len(b_set - o_set),
        "OKX_ONLY_TIMESTAMPS": len(o_set - b_set),
        "ALIGNMENT_RATE": (len(aligned) / len(e_set)) if e_set else None,
        "BINANCE_FIRST_UTC": ms_to_utc(b_unique[0]) if b_unique else None,
        "BINANCE_LAST_UTC": ms_to_utc(b_unique[-1]) if b_unique else None,
        "OKX_FIRST_UTC": ms_to_utc(o_unique[0]) if o_unique else None,
        "OKX_LAST_UTC": ms_to_utc(o_unique[-1]) if o_unique else None,
        "interpolation": False,
        "forward_fill": False,
        "bespoke_gap_repair": False,
    }
    assert_no_forbidden(report, where="census")
    return report


def collect_okx_window_times(raw_dir: Path, pages: list[dict[str, Any]]) -> list[int]:
    times: list[int] = []
    for page in pages:
        path = ARTIFACT_ROOT / page["path"]
        parsed = json.loads(path.read_text(encoding="utf-8"))
        for row in parsed.get("data") or []:
            ts = int(row[0])
            confirm = str(row[8]) if len(row) > 8 else ""
            if confirm != "1":
                continue
            if ts % BAR_MS != 0:
                continue
            if WINDOW_START_MS <= ts < WINDOW_END_EXCLUSIVE_MS:
                times.append(ts)
    return times


def collect_binance_times(raw_dir: Path) -> list[int]:
    times: list[int] = []
    for period in MONTHS:
        zip_path = raw_dir / f"BTCUSDT-5m-{period}.zip"
        with zipfile.ZipFile(zip_path) as zf:
            csv_members = [n for n in zf.namelist() if n.lower().endswith(".csv")]
            with zf.open(csv_members[0]) as handle:
                reader = csv.reader(io.TextIOWrapper(handle, encoding="utf-8", newline=""))
                for row in reader:
                    if not row or row[0].lower() in {"open_time", "open time"}:
                        continue
                    ts = int(row[0])
                    if WINDOW_START_MS <= ts < WINDOW_END_EXCLUSIVE_MS:
                        times.append(ts)
    return times


def write_json(path: Path, payload: Any) -> str:
    assert_no_forbidden(payload, where=str(path))
    data = json.dumps(payload, indent=2, sort_keys=True).encode("utf-8") + b"\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return sha256_bytes(data)


def main() -> int:
    ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
    DOCS_ROOT.mkdir(parents=True, exist_ok=True)
    binance_raw = ARTIFACT_ROOT / "raw" / "binance"
    okx_raw = ARTIFACT_ROOT / "raw" / "okx"
    binance_ledger = download_binance(binance_raw)
    okx_pages = download_okx(okx_raw)
    binance_times = collect_binance_times(binance_raw)
    okx_times = collect_okx_window_times(okx_raw, okx_pages)
    report = census(binance_times, okx_times)
    snapshot = {
        "schema": "signalbot_market_06_okx_binance_feasibility_snapshot",
        "schema_version": "1.0.0",
        "dataset_id": "MARKET_06_OKX_BINANCE_FEASIBILITY_V0",
        "scientific_outcomes_inspected": False,
        "dislocation_computed": False,
        "future_returns_computed": False,
        "2025_opened": False,
        "2026_opened": False,
        "window_start_utc": "2022-01-01T00:00:00Z",
        "window_end_exclusive_utc": "2025-01-01T00:00:00Z",
        "binance_checksums_verified": all(
            item["checksum_verification"] == "VERIFIED" for item in binance_ledger
        ),
        "binance_object_count": len(binance_ledger),
        "okx_page_count": len(okx_pages),
        "okx_all_pages_confirm_1": all(p.get("all_confirm_1", False) for p in okx_pages if p.get("n_records")),
        "okx_all_pages_5m_aligned": all(p.get("all_5m_aligned", False) for p in okx_pages if p.get("n_records")),
        "census": report,
        "materialized_utc": utc_now(),
        "raw_bytes_git_retained": False,
        "raw_bytes_location": str(ARTIFACT_ROOT / "raw"),
        "durability": "IDENTITY_PROVEN_AT_MATERIALIZATION_RAW_BYTES_NOT_GIT_RETAINED",
    }
    write_json(ARTIFACT_ROOT / "reports" / "binance_object_ledger.json", binance_ledger)
    write_json(ARTIFACT_ROOT / "reports" / "okx_page_manifest.json", okx_pages)
    write_json(ARTIFACT_ROOT / "reports" / "timestamp_census.json", report)
    write_json(ARTIFACT_ROOT / "reports" / "snapshot.json", snapshot)
    # Git-bound identity copies (no OHLC).
    for name in ("binance_object_ledger.json", "okx_page_manifest.json", "timestamp_census.json", "snapshot.json"):
        src = ARTIFACT_ROOT / "reports" / name
        dest = DOCS_ROOT / name
        dest.write_bytes(src.read_bytes())
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
