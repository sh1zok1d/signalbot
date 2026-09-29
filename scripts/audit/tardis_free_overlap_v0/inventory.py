"""Inventory free Tardis CSV.gz files. Does not interpret a gap as a zero."""
from __future__ import annotations

import gzip
import hashlib
import os
from datetime import datetime, timedelta, timezone

from .constants import (
    DERIVATIVE_TICKER_COLUMNS,
    SAMPLE_DATES,
    TRADE_COLUMNS,
    VENUES,
    file_url,
    vendor_filename,
)
from .parsing import SchemaError, exchange_us_to_datetime, iter_csv_rows, require_columns


def sha256_file(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        while True:
            block = handle.read(1 << 20)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def http_status_from_hdr(path: str) -> dict:
    hdr_path = path + ".hdr"
    if not os.path.exists(hdr_path):
        return {"http_status": None, "content_type": None, "content_length_header": None}
    status = None
    content_type = None
    content_length = None
    with open(hdr_path, "r", encoding="latin1") as handle:
        for line in handle:
            stripped = line.strip()
            if stripped.upper().startswith("HTTP/") and status is None:
                parts = stripped.split()
                if len(parts) >= 2 and parts[1].isdigit():
                    status = int(parts[1])
            lower = stripped.lower()
            if lower.startswith("content-type:"):
                content_type = stripped.split(":", 1)[1].strip()
            if lower.startswith("content-length:"):
                content_length = stripped.split(":", 1)[1].strip()
    return {
        "http_status": status,
        "content_type": content_type,
        "content_length_header": content_length,
    }


def _gzip_magic(path: str) -> bool:
    with open(path, "rb") as handle:
        return handle.read(2) == b"\x1f\x8b"


def inventory_file(path: str, *, venue, data_type: str, sample_date: str) -> dict:
    expected = TRADE_COLUMNS if data_type == "trades" else DERIVATIVE_TICKER_COLUMNS
    record = {
        "path_basename": os.path.basename(path),
        "url": file_url(venue, data_type, sample_date),
        "tardis_exchange": venue.tardis_exchange,
        "tardis_symbol": venue.tardis_symbol,
        "signalbot_exchange": venue.signalbot_exchange,
        "canonical_symbol": venue.canonical_symbol,
        "data_type": data_type,
        "sample_date": sample_date,
        "source": "TARDIS_FREE_SAMPLE",
        "compressed_bytes": os.path.getsize(path) if os.path.exists(path) else None,
        "sha256": None,
        "gzip_magic": None,
        "schema_ok": False,
        "schema_error": None,
        "header": None,
        "row_count": None,
        "first_timestamp": None,
        "last_timestamp": None,
        "rows_before_sample_date": None,
        "rows_at_or_after_sample_end": None,
        "timestamp_monotonic_non_decreasing": None,
        "side_counts": None,
        "open_interest_present_rows": None,
        "open_interest_empty_rows": None,
        "status": "MISSING",
    }
    record.update(http_status_from_hdr(path))
    if not os.path.exists(path):
        record["status"] = "MISSING"
        return record
    record["sha256"] = sha256_file(path)
    record["gzip_magic"] = _gzip_magic(path)
    if not record["gzip_magic"]:
        record["status"] = "SCHEMA_CHANGED"
        record["schema_error"] = "body is not gzip"
        return record
    if record["http_status"] not in (None, 200):
        record["status"] = "HTTP_NOT_OK"
        return record
    day = datetime.fromisoformat(sample_date).replace(tzinfo=timezone.utc)
    day_end = day + timedelta(days=1)
    try:
        rows = iter_csv_rows(path)
        header = list(next(rows))
        require_columns(header, expected, kind=data_type)
    except (SchemaError, gzip.BadGzipFile, OSError) as exc:
        record["status"] = "SCHEMA_CHANGED"
        record["schema_error"] = str(exc)
        return record
    record["header"] = header
    record["schema_ok"] = True
    ts_i = header.index("timestamp")
    side_i = header.index("side") if data_type == "trades" else None
    oi_i = header.index("open_interest") if data_type == "derivative_ticker" else None
    n = 0
    before = 0
    after = 0
    first_us = None
    last_us = None
    prev_us = None
    monotonic = True
    side_counts: dict[str, int] = {}
    oi_present = 0
    oi_empty = 0
    try:
        for raw in rows:
            if len(raw) != len(header):
                raise SchemaError("ragged row")
            us = int(raw[ts_i])
            if first_us is None:
                first_us = us
            if prev_us is not None and us < prev_us:
                monotonic = False
            prev_us = us
            last_us = us
            ts = exchange_us_to_datetime(us)
            if ts < day:
                before += 1
            elif ts >= day_end:
                after += 1
            n += 1
            if side_i is not None:
                side = raw[side_i]
                side_counts[side] = side_counts.get(side, 0) + 1
            if oi_i is not None:
                if raw[oi_i] == "":
                    oi_empty += 1
                else:
                    oi_present += 1
    except (SchemaError, ValueError, gzip.BadGzipFile) as exc:
        record["status"] = "SCHEMA_CHANGED"
        record["schema_error"] = str(exc)
        record["row_count"] = n
        return record
    record["row_count"] = n
    record["first_timestamp"] = (
        exchange_us_to_datetime(first_us).isoformat() if first_us is not None else None
    )
    record["last_timestamp"] = (
        exchange_us_to_datetime(last_us).isoformat() if last_us is not None else None
    )
    record["rows_before_sample_date"] = before
    record["rows_at_or_after_sample_end"] = after
    record["timestamp_monotonic_non_decreasing"] = monotonic
    record["side_counts"] = side_counts or None
    record["open_interest_present_rows"] = oi_present if oi_i is not None else None
    record["open_interest_empty_rows"] = oi_empty if oi_i is not None else None
    record["status"] = "OK"
    return record


def inventory_vendor_dir(vendor_dir: str) -> list[dict]:
    records = []
    for sample_date in SAMPLE_DATES:
        for venue in VENUES:
            for data_type in ("derivative_ticker", "trades"):
                name = vendor_filename(venue, data_type, sample_date)
                path = os.path.join(vendor_dir, name)
                records.append(inventory_file(
                    path, venue=venue, data_type=data_type, sample_date=sample_date,
                ))
    return records
