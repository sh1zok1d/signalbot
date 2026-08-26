"""Deterministic CORE_BTC_BINANCE_V0 materialization helpers.

Network-free except where the caller injects a fetch function. Reuses the
hardened PR #71 checksum / ZIP-member / CSV / invariant machinery in
`core_btc_binance_v0_probe_lib`. Does not promote
`docs/manifests/CORE_BTC_BINANCE_V0.yaml` and does not invent dataset
semantics beyond that contract.

This module is the implementation of the eventual 2020-01-01T00:00:00Z ..
2026-08-26T00:00:00Z pipeline. It does not itself download bulk history.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Callable, Optional

from scripts.research.core_btc_binance_v0_probe_lib import (
    ARCHIVE_ROOT_DAILY,
    ARCHIVE_ROOT_MONTHLY,
    BAR_MS,
    INTERVAL,
    MARKET_TYPE,
    PROVIDER,
    SYMBOL,
    audit_klines_window,
    bar_end_exclusive_ms,
    daily_archive_object_name,
    daily_archive_urls,
    daily_expected_csv_member_name,
    day_bounds_ms,
    decide_existing_zip_disposition,
    evaluate_checksum_verification,
    expected_csv_member_name,
    local_checksum_filename,
    local_zip_filename,
    month_bounds_ms,
    parse_checksum_text,
    parse_kline_csv,
    read_kline_csv_member_named,
    row_invariant_violations,
    sha256_of_bytes,
    sha256_of_file,
    CoreBtcBinanceV0ProbeError,
)

UTC = timezone.utc

DATASET_ID = "CORE_BTC_BINANCE_V0"
CONTRACT_PATH = "docs/CORE_BTC_BINANCE_V0_CONTRACT.md"
REPO_MANIFEST_PATH = "docs/manifests/CORE_BTC_BINANCE_V0.yaml"
MATERIALIZER_VERSION = 1
CANONICALIZATION_VERSION = 1
AGGREGATION_VERSION = 1
REPORT_SCHEMA_VERSION = 1
TOOL_KIND = "CORE_BTC_BINANCE_V0_MATERIALIZER"

FROZEN_START_INCLUSIVE = datetime(2020, 1, 1, tzinfo=UTC)
FROZEN_END_EXCLUSIVE = datetime(2026, 8, 26, tzinfo=UTC)
MONTHLY_START = "2020-01"
MONTHLY_END = "2026-07"
DAILY_START = "2026-08-01"
DAILY_END = "2026-08-25"

DEFAULT_DISK_RESERVE_BYTES = 5 * 1024 * 1024 * 1024
# Conservative per-object body estimates used only when HEAD has no length.
CONSERVATIVE_MONTHLY_ZIP_BYTES = 8 * 1024 * 1024
CONSERVATIVE_DAILY_ZIP_BYTES = 256 * 1024
CHECKSUM_BYTES_ESTIMATE = 128

# Predeclared gap-quality diagnostic (NOT an edge rule, NOT tuned on
# observed gaps). Adjacent 1m bars are "extreme" when |close/open - 1| or
# base_volume is at or above the 99th percentile of the observed canonical
# 1m population. Documented in the materialization runbook.
GAP_EXTREME_PERCENTILE = 99

HTF_SPEC = (
    ("5m", 5),
    ("15m", 15),
    ("1h", 60),
    ("4h", 240),
)

DECIMAL_FIELDS = (
    "open", "high", "low", "close",
    "base_volume", "quote_volume",
    "taker_buy_base_volume", "taker_buy_quote_volume",
    "taker_sell_base_volume", "taker_sell_quote_volume",
)


class CoreBtcBinanceV0MaterializerError(ValueError):
    """Malformed materializer inputs or fail-closed disk/revision errors."""


# ---------------------------------------------------------------------------
# frozen source plan
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class SourceObject:
    archive_class: str  # monthly | daily
    source_period: str  # YYYY-MM or YYYY-MM-DD
    source_url: str
    checksum_url: str
    expected_zip_filename: str
    expected_csv_member_name: str
    period_start_ms: int
    period_end_exclusive_ms: int

    def as_plan_dict(self) -> dict:
        return {
            "provider": PROVIDER,
            "market_type": MARKET_TYPE,
            "symbol": SYMBOL,
            "interval": INTERVAL,
            "archive_class": self.archive_class,
            "source_period": self.source_period,
            "source_url": self.source_url,
            "checksum_url": self.checksum_url,
            "expected_zip_filename": self.expected_zip_filename,
            "expected_csv_member_name": self.expected_csv_member_name,
            "period_start_ms": self.period_start_ms,
            "period_end_exclusive_ms": self.period_end_exclusive_ms,
        }


def _iter_year_months(start: str, end: str) -> list[str]:
    y, m = (int(p) for p in start.split("-"))
    ey, em = (int(p) for p in end.split("-"))
    out = []
    while (y, m) <= (ey, em):
        out.append(f"{y:04d}-{m:02d}")
        m += 1
        if m == 13:
            m = 1
            y += 1
    return out


def _iter_days(start: str, end: str) -> list[str]:
    cur = datetime.fromisoformat(start).replace(tzinfo=UTC)
    last = datetime.fromisoformat(end).replace(tzinfo=UTC)
    out = []
    while cur <= last:
        out.append(cur.date().isoformat())
        cur += timedelta(days=1)
    return out


def build_frozen_source_plan() -> list[SourceObject]:
    """Exact contract source layout: monthly 2020-01..2026-07 then daily
    2026-08-01..2026-08-25, deterministic order."""
    objects: list[SourceObject] = []
    for ym in _iter_year_months(MONTHLY_START, MONTHLY_END):
        zip_url, checksum_url = (
            f"{ARCHIVE_ROOT_MONTHLY}/{SYMBOL}/{INTERVAL}/{local_zip_filename(ym)}",
            f"{ARCHIVE_ROOT_MONTHLY}/{SYMBOL}/{INTERVAL}/{local_checksum_filename(ym)}",
        )
        start_ms, end_ms = month_bounds_ms(ym)
        objects.append(SourceObject(
            archive_class="monthly",
            source_period=ym,
            source_url=zip_url,
            checksum_url=checksum_url,
            expected_zip_filename=local_zip_filename(ym),
            expected_csv_member_name=expected_csv_member_name(ym),
            period_start_ms=start_ms,
            period_end_exclusive_ms=end_ms,
        ))
    for ymd in _iter_days(DAILY_START, DAILY_END):
        zip_url, checksum_url = daily_archive_urls(ymd)
        start_ms, end_ms = day_bounds_ms(ymd)
        objects.append(SourceObject(
            archive_class="daily",
            source_period=ymd,
            source_url=zip_url,
            checksum_url=checksum_url,
            expected_zip_filename=daily_archive_object_name(ymd),
            expected_csv_member_name=daily_expected_csv_member_name(ymd),
            period_start_ms=start_ms,
            period_end_exclusive_ms=end_ms,
        ))
    return objects


def frozen_range_ms() -> tuple[int, int]:
    start = int(FROZEN_START_INCLUSIVE.timestamp() * 1000)
    end = int(FROZEN_END_EXCLUSIVE.timestamp() * 1000)
    return start, end


def expected_global_minute_count() -> int:
    start, end = frozen_range_ms()
    return (end - start) // BAR_MS


# ---------------------------------------------------------------------------
# dataset layout
# ---------------------------------------------------------------------------
def dataset_layout(root: Path) -> dict[str, Path]:
    root = Path(root)
    return {
        "root": root,
        "raw": root / "raw",
        "raw_monthly": root / "raw" / "monthly",
        "raw_daily": root / "raw" / "daily",
        "canonical": root / "canonical",
        "canonical_1m_monthly": root / "canonical" / "1m" / "monthly",
        "canonical_1m_daily": root / "canonical" / "1m" / "daily",
        "canonical_htf": root / "canonical",
        "reports": root / "reports",
        "manifests": root / "manifests",
    }


def raw_dir_for(root: Path, obj: SourceObject) -> Path:
    layout = dataset_layout(root)
    base = layout["raw_monthly"] if obj.archive_class == "monthly" else layout["raw_daily"]
    return base / obj.source_period


def raw_zip_path(root: Path, obj: SourceObject) -> Path:
    return raw_dir_for(root, obj) / obj.expected_zip_filename


def raw_checksum_path(root: Path, obj: SourceObject) -> Path:
    return raw_dir_for(root, obj) / f"{obj.expected_zip_filename}.CHECKSUM"


def canonical_1m_path(root: Path, obj: SourceObject) -> Path:
    layout = dataset_layout(root)
    if obj.archive_class == "monthly":
        return layout["canonical_1m_monthly"] / f"{obj.source_period}.parquet"
    return layout["canonical_1m_daily"] / f"{obj.source_period}.parquet"


def htf_path(root: Path, interval: str) -> Path:
    return dataset_layout(root)["canonical_htf"] / interval / "bars.parquet"


def atomic_write_bytes(path: Path, data: bytes) -> None:
    """Temp file in the destination directory + os.replace. Partial `.tmp`
    / leftover files are never dataset evidence."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
        os.replace(tmp_name, path)
    except BaseException:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def atomic_write_text(path: Path, text: str) -> None:
    atomic_write_bytes(path, text.encode("utf-8"))


def dumps_deterministic(payload: dict) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def write_json(path: Path, payload: dict) -> None:
    atomic_write_text(path, dumps_deterministic(payload))


def discard_partial_files(directory: Path) -> list[str]:
    """`.part` / leftover `.tmp` files are never admitted as evidence."""
    removed = []
    if not directory.exists():
        return removed
    for path in directory.iterdir():
        if path.suffix in {".part", ".tmp"} or ".part." in path.name:
            path.unlink()
            removed.append(path.name)
        elif path.name.startswith(".") and path.name.endswith(".tmp"):
            path.unlink()
            removed.append(path.name)
    return removed


# ---------------------------------------------------------------------------
# plan / inventory / disk
# ---------------------------------------------------------------------------
def plan_report(objects: list[SourceObject], git_commit_sha: str = "UNKNOWN") -> dict:
    monthly = [o for o in objects if o.archive_class == "monthly"]
    daily = [o for o in objects if o.archive_class == "daily"]
    start_ms, end_ms = frozen_range_ms()
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "report_kind": "CORE_BTC_BINANCE_V0_SOURCE_PLAN",
        "dataset_id": DATASET_ID,
        "contract_path": CONTRACT_PATH,
        "manifest_path": REPO_MANIFEST_PATH,
        "materializer_version": MATERIALIZER_VERSION,
        "provenance_git_commit_sha": git_commit_sha,
        "provider": PROVIDER,
        "market_type": MARKET_TYPE,
        "symbol": SYMBOL,
        "interval": INTERVAL,
        "start_inclusive": FROZEN_START_INCLUSIVE.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "end_exclusive": FROZEN_END_EXCLUSIVE.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "start_inclusive_ms": start_ms,
        "end_exclusive_ms": end_ms,
        "expected_1m_rows": expected_global_minute_count(),
        "monthly_range": {"start": MONTHLY_START, "end": MONTHLY_END, "count": len(monthly)},
        "daily_range": {"start": DAILY_START, "end": DAILY_END, "count": len(daily)},
        "source_object_count": len(objects),
        "objects": [o.as_plan_dict() for o in objects],
        "acceptance_note": (
            "This plan is not acquisition and not dataset acceptance. "
            f"{REPO_MANIFEST_PATH} stays PLANNED_NOT_MATERIALIZED / "
            "research_authorized: false until a later deliberate promotion."
        ),
    }


def estimate_object_bytes(archive_class: str, content_length: Optional[int]) -> tuple[int, str]:
    if content_length is not None and content_length >= 0:
        return content_length, "HEAD_CONTENT_LENGTH"
    if archive_class == "monthly":
        return CONSERVATIVE_MONTHLY_ZIP_BYTES, "CONSERVATIVE_DEFAULT_MONTHLY"
    return CONSERVATIVE_DAILY_ZIP_BYTES, "CONSERVATIVE_DEFAULT_DAILY"


def disk_usage_for(path: Path) -> dict:
    path.mkdir(parents=True, exist_ok=True)
    usage = shutil.disk_usage(path)
    return {
        "path": str(path),
        "total_bytes": usage.total,
        "used_bytes": usage.used,
        "free_bytes": usage.free,
    }


def retained_raw_size(root: Path) -> int:
    raw = dataset_layout(root)["raw"]
    if not raw.exists():
        return 0
    total = 0
    for dirpath, _dirnames, filenames in os.walk(raw):
        for name in filenames:
            if name.endswith(".part") or name.endswith(".tmp"):
                continue
            total += (Path(dirpath) / name).stat().st_size
    return total


def materialized_size(root: Path) -> int:
    canonical = dataset_layout(root)["canonical"]
    if not canonical.exists():
        return 0
    total = 0
    for dirpath, _dirnames, filenames in os.walk(canonical):
        for name in filenames:
            total += (Path(dirpath) / name).stat().st_size
    return total


def assert_disk_budget(
    root: Path,
    estimated_download_bytes: int,
    disk_reserve_bytes: int = DEFAULT_DISK_RESERVE_BYTES,
    extra_temp_bytes: Optional[int] = None,
) -> dict:
    """Fail closed if free space minus reserve cannot hold the remaining
    download plus a conservative temp bound (one in-flight ZIP)."""
    usage = disk_usage_for(root)
    already = retained_raw_size(root)
    remaining = max(0, estimated_download_bytes - already)
    temp_bound = extra_temp_bytes if extra_temp_bytes is not None else CONSERVATIVE_MONTHLY_ZIP_BYTES
    need = remaining + temp_bound + disk_reserve_bytes
    ok = usage["free_bytes"] >= need
    report = {
        **usage,
        "estimated_raw_download_bytes": estimated_download_bytes,
        "retained_raw_bytes": already,
        "remaining_download_bytes": remaining,
        "temp_bound_bytes": temp_bound,
        "disk_reserve_bytes": disk_reserve_bytes,
        "bytes_required_including_reserve": need,
        "disk_safety_ok": ok,
    }
    if not ok:
        raise CoreBtcBinanceV0MaterializerError(
            "disk-safety gate failed: "
            f"free={usage['free_bytes']} required={need} "
            f"(remaining_download={remaining} + temp={temp_bound} + reserve={disk_reserve_bytes})"
        )
    return report


# ---------------------------------------------------------------------------
# acquire
# ---------------------------------------------------------------------------
FetchFn = Callable[[str], tuple[Optional[bytes], str, Optional[int]]]
# returns (body_or_none, status_str like HTTP_200 / HTTP_403 / NETWORK_ERROR:..., content_length)


def acquire_one_object(
    root: Path, obj: SourceObject, fetch: FetchFn, now_iso: str,
) -> dict:
    dest_dir = raw_dir_for(root, obj)
    dest_dir.mkdir(parents=True, exist_ok=True)
    discarded = discard_partial_files(dest_dir)
    zip_path = raw_zip_path(root, obj)
    checksum_path = raw_checksum_path(root, obj)
    record = {
        **obj.as_plan_dict(),
        "attempted": True,
        "downloaded_at_utc": now_iso,
        "discarded_partial_files": discarded,
        "source_status": "NOT_REQUESTED",
        "checksum_http_status": None,
        "checksum_observed_filename": None,
        "expected_sha256": None,
        "expected_sha256_status": "NOT_REQUESTED",
        "local_sha256": None,
        "checksum_verification": "NOT_ATTEMPTED",
        "byte_size": None,
        "disposition": None,
    }

    checksum_bytes, checksum_status, _cl = fetch(obj.checksum_url)
    record["checksum_http_status"] = checksum_status
    parsed = None
    if checksum_bytes is not None:
        try:
            parsed = parse_checksum_text(checksum_bytes.decode("utf-8", errors="replace"))
            record["expected_sha256"] = parsed["sha256"]
            record["checksum_observed_filename"] = parsed["filename"]
            record["expected_sha256_status"] = "PRESENT"
        except CoreBtcBinanceV0ProbeError as exc:
            record["expected_sha256_status"] = f"MALFORMED: {exc}"
    else:
        record["expected_sha256_status"] = f"MISSING: {checksum_status}"

    existing_sha = sha256_of_file(zip_path) if zip_path.exists() else None
    disposition = decide_existing_zip_disposition(existing_sha, record.get("expected_sha256"))
    record["disposition"] = disposition

    if disposition == "REVISION_CONFLICT":
        record["source_status"] = "REVISION_CONFLICT"
        record["local_sha256"] = existing_sha
        record["byte_size"] = zip_path.stat().st_size
        record["checksum_verification"] = evaluate_checksum_verification(
            existing_sha, parsed, obj.expected_zip_filename)
        # RT-05: do not overwrite the existing sidecar.
        return record

    if disposition in ("REUSED_IDENTICAL", "REUSED_UNVERIFIED_NO_REFERENCE"):
        record["source_status"] = disposition
        record["local_sha256"] = existing_sha
        record["byte_size"] = zip_path.stat().st_size
        if checksum_bytes is not None and parsed is not None and not checksum_path.exists():
            atomic_write_bytes(checksum_path, checksum_bytes)
        record["checksum_verification"] = evaluate_checksum_verification(
            existing_sha, parsed, obj.expected_zip_filename)
        return record

    zip_bytes, zip_status, _cl = fetch(obj.source_url)
    if zip_bytes is None:
        record["source_status"] = zip_status
        return record

    part_path = zip_path.with_suffix(zip_path.suffix + ".part")
    try:
        atomic_write_bytes(part_path, zip_bytes)
        os.replace(part_path, zip_path)
    finally:
        if part_path.exists():
            try:
                part_path.unlink()
            except OSError:
                pass

    if checksum_bytes is not None and parsed is not None and not checksum_path.exists():
        atomic_write_bytes(checksum_path, checksum_bytes)

    record["source_status"] = "HTTP_200"
    record["byte_size"] = len(zip_bytes)
    record["local_sha256"] = sha256_of_bytes(zip_bytes)
    record["checksum_verification"] = evaluate_checksum_verification(
        record["local_sha256"], parsed, obj.expected_zip_filename)
    return record


# ---------------------------------------------------------------------------
# audit-raw / materialize
# ---------------------------------------------------------------------------
@dataclass
class CanonicalBar:
    open_time_ms: int
    bar_end_exclusive_ms: int
    available_at_ms: int
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    base_volume: Decimal
    quote_volume: Decimal
    trade_count: int
    taker_buy_base_volume: Decimal
    taker_buy_quote_volume: Decimal
    taker_sell_base_volume: Decimal
    taker_sell_quote_volume: Decimal
    source_period: str
    archive_class: str
    source_sha256: str

    def semantic_tuple(self) -> tuple:
        return (
            self.open_time_ms, self.open, self.high, self.low, self.close,
            self.base_volume, self.quote_volume, self.trade_count,
            self.taker_buy_base_volume, self.taker_buy_quote_volume,
        )


def kline_to_canonical(row, obj: SourceObject, source_sha256: str) -> CanonicalBar:
    bar_end = bar_end_exclusive_ms(row.open_time_ms)
    return CanonicalBar(
        open_time_ms=row.open_time_ms,
        bar_end_exclusive_ms=bar_end,
        available_at_ms=bar_end,
        open=row.open,
        high=row.high,
        low=row.low,
        close=row.close,
        base_volume=row.base_volume,
        quote_volume=row.quote_volume,
        trade_count=row.trade_count,
        taker_buy_base_volume=row.taker_buy_base_volume,
        taker_buy_quote_volume=row.taker_buy_quote_volume,
        taker_sell_base_volume=row.base_volume - row.taker_buy_base_volume,
        taker_sell_quote_volume=row.quote_volume - row.taker_buy_quote_volume,
        source_period=obj.source_period,
        archive_class=obj.archive_class,
        source_sha256=source_sha256,
    )


def audit_raw_object(root: Path, obj: SourceObject) -> dict:
    zip_path = raw_zip_path(root, obj)
    checksum_path = raw_checksum_path(root, obj)
    record = {
        **obj.as_plan_dict(),
        "attempted": True,
        "byte_size": None,
        "local_sha256": None,
        "expected_sha256": None,
        "checksum_observed_filename": None,
        "checksum_verification": "NOT_ATTEMPTED",
        "zip_member_names": None,
        "parser_status": "NOT_ATTEMPTED",
        "admitted_to_canonical": False,
    }
    if zip_path.exists() and zip_path.suffix == ".part":
        record["parser_status"] = "PARTIAL_FILE_NOT_EVIDENCE"
        return record
    if not zip_path.exists():
        record["parser_status"] = "NO_SUCH_FILE"
        record["checksum_verification"] = "NOT_VERIFIABLE_MISSING_CHECKSUM"
        return record

    record["byte_size"] = zip_path.stat().st_size
    record["local_sha256"] = sha256_of_file(zip_path)
    parsed = None
    if checksum_path.exists():
        try:
            parsed = parse_checksum_text(checksum_path.read_text(encoding="utf-8"))
            record["expected_sha256"] = parsed["sha256"]
            record["checksum_observed_filename"] = parsed["filename"]
        except CoreBtcBinanceV0ProbeError as exc:
            record["checksum_verification"] = "NOT_VERIFIABLE_MISSING_CHECKSUM"
            record["expected_sha256_status"] = f"MALFORMED: {exc}"
            return record
    record["checksum_verification"] = evaluate_checksum_verification(
        record["local_sha256"], parsed, obj.expected_zip_filename)

    csv_text, names, parser_status = read_kline_csv_member_named(
        zip_path, obj.expected_csv_member_name)
    record["zip_member_names"] = names
    record["parser_status"] = parser_status
    if parser_status != "OK" or csv_text is None:
        return record

    rows, parse_meta = parse_kline_csv(csv_text)
    audit = audit_klines_window(
        rows, obj.period_start_ms, obj.period_end_exclusive_ms,
        parse_meta["malformed_row_count"])
    record["header_present"] = parse_meta["header_present"]
    record.update(audit)
    record["admitted_to_canonical"] = record["checksum_verification"] == "VERIFIED"
    return record


def _dec_str(value: Decimal) -> str:
    return format(value, "f")


def canonical_rows_to_parquet_bytes(rows: list[CanonicalBar]) -> bytes:
    import pyarrow as pa
    import pyarrow.parquet as pq

    rows_sorted = sorted(rows, key=lambda r: r.open_time_ms)
    arrays = {
        "open_time_ms": pa.array([r.open_time_ms for r in rows_sorted], type=pa.int64()),
        "bar_end_exclusive_ms": pa.array([r.bar_end_exclusive_ms for r in rows_sorted], type=pa.int64()),
        "available_at_ms": pa.array([r.available_at_ms for r in rows_sorted], type=pa.int64()),
        "trade_count": pa.array([r.trade_count for r in rows_sorted], type=pa.int64()),
        "source_period": pa.array([r.source_period for r in rows_sorted], type=pa.string()),
        "archive_class": pa.array([r.archive_class for r in rows_sorted], type=pa.string()),
        "source_sha256": pa.array([r.source_sha256 for r in rows_sorted], type=pa.string()),
    }
    for name in DECIMAL_FIELDS:
        arrays[name] = pa.array([_dec_str(getattr(r, name)) for r in rows_sorted], type=pa.string())
    table = pa.table(arrays)
    buf = pa.BufferOutputStream()
    pq.write_table(table, buf, compression="zstd")
    return buf.getvalue().to_pybytes()


def canonical_rows_from_parquet(path: Path) -> list[CanonicalBar]:
    import pyarrow.parquet as pq

    table = pq.read_table(path)
    cols = {name: table.column(name).to_pylist() for name in table.column_names}
    n = table.num_rows
    out = []
    for i in range(n):
        out.append(CanonicalBar(
            open_time_ms=int(cols["open_time_ms"][i]),
            bar_end_exclusive_ms=int(cols["bar_end_exclusive_ms"][i]),
            available_at_ms=int(cols["available_at_ms"][i]),
            open=Decimal(cols["open"][i]),
            high=Decimal(cols["high"][i]),
            low=Decimal(cols["low"][i]),
            close=Decimal(cols["close"][i]),
            base_volume=Decimal(cols["base_volume"][i]),
            quote_volume=Decimal(cols["quote_volume"][i]),
            trade_count=int(cols["trade_count"][i]),
            taker_buy_base_volume=Decimal(cols["taker_buy_base_volume"][i]),
            taker_buy_quote_volume=Decimal(cols["taker_buy_quote_volume"][i]),
            taker_sell_base_volume=Decimal(cols["taker_sell_base_volume"][i]),
            taker_sell_quote_volume=Decimal(cols["taker_sell_quote_volume"][i]),
            source_period=cols["source_period"][i],
            archive_class=cols["archive_class"][i],
            source_sha256=cols["source_sha256"][i],
        ))
    return out


def materialize_object_1m(root: Path, obj: SourceObject, audit_record: dict) -> dict:
    """Parse a VERIFIED zip into a canonical 1m parquet partition.

    Identical duplicate rows: keep the first in file order and record.
    Conflicting duplicates: drop the minute from this partition and record.
    Rows failing invariants / outside the object period / outside the frozen
    global range are rejected, never repaired.
    """
    result = {
        "source_period": obj.source_period,
        "archive_class": obj.archive_class,
        "canonical_path": None,
        "admitted_rows": 0,
        "identical_duplicate_count": 0,
        "conflicting_duplicate_open_times": [],
        "rejected_schema": audit_record.get("malformed_row_count") or 0,
        "rejected_invariant": 0,
        "rejected_identity": 0,
        "rejected_end_exclusive": 0,
    }
    if audit_record.get("checksum_verification") != "VERIFIED":
        result["status"] = "SKIPPED_NOT_VERIFIED"
        return result
    if audit_record.get("parser_status") != "OK":
        result["status"] = "SKIPPED_PARSER"
        return result

    zip_path = raw_zip_path(root, obj)
    csv_text, _names, status = read_kline_csv_member_named(zip_path, obj.expected_csv_member_name)
    if status != "OK" or csv_text is None:
        result["status"] = "SKIPPED_PARSER"
        return result
    rows, _meta = parse_kline_csv(csv_text)
    global_start, global_end = frozen_range_ms()
    by_time: dict[int, CanonicalBar] = {}
    identical = 0
    conflicts: set[int] = set()
    rejected_invariant = 0
    rejected_identity = 0
    rejected_end = 0
    sha = audit_record["local_sha256"]

    for row in rows:
        if row_invariant_violations(row):
            rejected_invariant += 1
            continue
        if not (obj.period_start_ms <= row.open_time_ms < obj.period_end_exclusive_ms):
            rejected_identity += 1
            continue
        if row.open_time_ms < global_start or row.open_time_ms >= global_end:
            rejected_end += 1
            continue
        bar = kline_to_canonical(row, obj, sha)
        existing = by_time.get(bar.open_time_ms)
        if existing is None:
            by_time[bar.open_time_ms] = bar
            continue
        if existing.semantic_tuple() == bar.semantic_tuple():
            identical += 1
            continue
        conflicts.add(bar.open_time_ms)
        by_time.pop(bar.open_time_ms, None)

    for t in conflicts:
        by_time.pop(t, None)

    accepted = [by_time[t] for t in sorted(by_time)]
    out_path = canonical_1m_path(root, obj)
    payload = canonical_rows_to_parquet_bytes(accepted)
    result["canonical_path"] = str(out_path.relative_to(root)).replace("\\", "/")
    result["admitted_rows"] = len(accepted)
    result["identical_duplicate_count"] = identical
    result["conflicting_duplicate_open_times"] = sorted(conflicts)
    result["rejected_invariant"] = rejected_invariant
    result["rejected_identity"] = rejected_identity
    result["rejected_end_exclusive"] = rejected_end
    if out_path.exists() and sha256_of_file(out_path) == sha256_of_bytes(payload):
        result["status"] = "REUSED_IDENTICAL_PARTITION"
        return result
    atomic_write_bytes(out_path, payload)
    result["status"] = "WROTE"
    return result


def load_all_canonical_1m(root: Path, objects: list[SourceObject]) -> list[CanonicalBar]:
    bars: list[CanonicalBar] = []
    for obj in objects:
        path = canonical_1m_path(root, obj)
        if path.exists():
            bars.extend(canonical_rows_from_parquet(path))
    bars.sort(key=lambda r: r.open_time_ms)
    return bars


def merge_cross_object(
    bars: list[CanonicalBar],
) -> tuple[list[CanonicalBar], dict]:
    """Detect cross-object overlap. Identical: keep the earlier source_period
    (plan order is chronological). Conflicting: drop both and record."""
    by_time: dict[int, CanonicalBar] = {}
    identical = 0
    conflicts: list[int] = []
    conflict_set: set[int] = set()
    for bar in bars:
        if bar.open_time_ms in conflict_set:
            continue
        existing = by_time.get(bar.open_time_ms)
        if existing is None:
            by_time[bar.open_time_ms] = bar
            continue
        if existing.semantic_tuple() == bar.semantic_tuple():
            identical += 1
            continue
        conflict_set.add(bar.open_time_ms)
        conflicts.append(bar.open_time_ms)
        by_time.pop(bar.open_time_ms, None)
    kept = [by_time[t] for t in sorted(by_time)]
    stats = {
        "cross_object_identical_duplicate_count": identical,
        "cross_object_conflicting_duplicate_open_times": sorted(set(conflicts)),
        "cross_object_conflicting_duplicate_count": len(set(conflicts)),
    }
    return kept, stats


# ---------------------------------------------------------------------------
# continuity / gap diagnostic / HTF / snapshot
# ---------------------------------------------------------------------------
def continuity_audit(
    bars: list[CanonicalBar],
    start_ms: Optional[int] = None,
    end_ms: Optional[int] = None,
) -> dict:
    if start_ms is None or end_ms is None:
        start_ms, end_ms = frozen_range_ms()
    expected = list(range(start_ms, end_ms, BAR_MS))
    expected_set = set(expected)
    times = [b.open_time_ms for b in bars]
    counts: dict[int, int] = {}
    for t in times:
        counts[t] = counts.get(t, 0) + 1
    unique = set(times)
    missing = sorted(expected_set - unique)
    extra = sorted(t for t in unique if t not in expected_set)
    duplicate_times = sorted(t for t, c in counts.items() if c > 1)
    ranges_incl = _compress(missing, BAR_MS)
    gaps = []
    longest = 0
    for a, b in ranges_incl:
        missing_minutes = ((b - a) // BAR_MS) + 1
        longest = max(longest, missing_minutes)
        gaps.append({
            "start_ms": a,
            "end_exclusive_ms": b + BAR_MS,
            "missing_minutes": missing_minutes,
        })
    by_year: dict[str, int] = {}
    by_month: dict[str, int] = {}
    for t in missing:
        dt = datetime.fromtimestamp(t / 1000, tz=UTC)
        year = f"{dt.year:04d}"
        month = f"{dt.year:04d}-{dt.month:02d}"
        by_year[year] = by_year.get(year, 0) + 1
        by_month[month] = by_month.get(month, 0) + 1
    return {
        "start_inclusive_ms": start_ms,
        "end_exclusive_ms": end_ms,
        "expected_minute_count": len(expected),
        "observed_rows": len(bars),
        "observed_unique_timestamps": len(unique),
        "missing_minute_count": len(missing),
        "duplicate_minute_count": sum(c - 1 for c in counts.values() if c > 1),
        "duplicate_open_times": duplicate_times,
        "rows_outside_frozen_range": extra,
        "longest_contiguous_gap_minutes": longest,
        "gaps": gaps,
        "missingness_by_year": {k: by_year[k] for k in sorted(by_year)},
        "missingness_by_month": {k: by_month[k] for k in sorted(by_month)},
        "first_observed_open_time_ms": times[0] if times else None,
        "last_observed_open_time_ms": times[-1] if times else None,
        "is_strictly_ordered": all(times[i] < times[i + 1] for i in range(len(times) - 1)),
    }


def _compress(sorted_values: list[int], step: int) -> list[list[int]]:
    if not sorted_values:
        return []
    ranges: list[list[int]] = []
    start = prev = sorted_values[0]
    for value in sorted_values[1:]:
        if value == prev + step:
            prev = value
            continue
        ranges.append([start, prev])
        start = prev = value
    ranges.append([start, prev])
    return ranges


def _percentile(sorted_values: list[Decimal], percentile: int) -> Optional[Decimal]:
    if not sorted_values:
        return None
    if percentile <= 0:
        return sorted_values[0]
    if percentile >= 100:
        return sorted_values[-1]
    idx = (percentile * len(sorted_values) + 99) // 100 - 1
    idx = min(max(idx, 0), len(sorted_values) - 1)
    return sorted_values[idx]


def gap_extreme_diagnostic(bars: list[CanonicalBar], gaps: list[dict]) -> dict:
    """Predeclared quality diagnostic. Does not repair or exclude gaps."""
    abs_returns: list[Decimal] = []
    volumes: list[Decimal] = []
    by_time = {b.open_time_ms: b for b in bars}
    for b in bars:
        if b.open > 0:
            abs_returns.append(abs(b.close / b.open - 1))
        volumes.append(b.base_volume)
    abs_returns.sort()
    volumes.sort()
    p_ret = _percentile(abs_returns, GAP_EXTREME_PERCENTILE)
    p_vol = _percentile(volumes, GAP_EXTREME_PERCENTILE)
    flagged = []
    for gap in gaps:
        before_t = gap["start_ms"] - BAR_MS
        after_t = gap["end_exclusive_ms"]
        adj = [by_time[t] for t in (before_t, after_t) if t in by_time]
        extreme = False
        reasons = []
        for bar in adj:
            if bar.open > 0 and p_ret is not None:
                ret = abs(bar.close / bar.open - 1)
                if ret >= p_ret:
                    extreme = True
                    reasons.append("adjacent_abs_return_ge_p99")
            if p_vol is not None and bar.base_volume >= p_vol:
                extreme = True
                reasons.append("adjacent_volume_ge_p99")
        flagged.append({
            **gap,
            "adjacent_open_time_ms": [b.open_time_ms for b in adj],
            "extreme_adjacent": extreme,
            "reasons": sorted(set(reasons)),
        })
    return {
        "rule": (
            f"An adjacent 1m bar is extreme when |close/open-1| or base_volume "
            f"is at or above the {GAP_EXTREME_PERCENTILE}th percentile of the "
            "observed canonical 1m population. Predeclared; not an edge rule; "
            "does not repair or drop gaps."
        ),
        "percentile": GAP_EXTREME_PERCENTILE,
        "p99_abs_return": None if p_ret is None else _dec_str(p_ret),
        "p99_base_volume": None if p_vol is None else _dec_str(p_vol),
        "gaps": flagged,
        "extreme_gap_count": sum(1 for g in flagged if g["extreme_adjacent"]),
    }


@dataclass
class HtfBar:
    open_time_ms: int
    bar_end_exclusive_ms: int
    available_at_ms: int
    is_complete: bool
    expected_constituents: int
    observed_constituents: int
    open: Optional[Decimal]
    high: Optional[Decimal]
    low: Optional[Decimal]
    close: Optional[Decimal]
    base_volume: Optional[Decimal]
    quote_volume: Optional[Decimal]
    trade_count: Optional[int]
    taker_buy_base_volume: Optional[Decimal]
    taker_buy_quote_volume: Optional[Decimal]
    taker_sell_base_volume: Optional[Decimal]
    taker_sell_quote_volume: Optional[Decimal]


def aggregate_htf(
    bars: list[CanonicalBar],
    minutes: int,
    start_ms: Optional[int] = None,
    end_ms: Optional[int] = None,
) -> list[HtfBar]:
    if start_ms is None or end_ms is None:
        start_ms, end_ms = frozen_range_ms()
    step = minutes * BAR_MS
    if start_ms % step != 0:
        raise CoreBtcBinanceV0MaterializerError(
            f"window start {start_ms} is not aligned to {minutes}m")
    by_time = {b.open_time_ms: b for b in bars}
    out: list[HtfBar] = []
    bucket = start_ms
    while bucket < end_ms:
        members = [by_time.get(bucket + i * BAR_MS) for i in range(minutes)]
        present = [m for m in members if m is not None]
        complete = len(present) == minutes
        bar_end = bucket + step
        if complete:
            out.append(HtfBar(
                open_time_ms=bucket,
                bar_end_exclusive_ms=bar_end,
                available_at_ms=bar_end,
                is_complete=True,
                expected_constituents=minutes,
                observed_constituents=minutes,
                open=present[0].open,
                high=max(m.high for m in present),
                low=min(m.low for m in present),
                close=present[-1].close,
                base_volume=sum((m.base_volume for m in present), Decimal(0)),
                quote_volume=sum((m.quote_volume for m in present), Decimal(0)),
                trade_count=sum(m.trade_count for m in present),
                taker_buy_base_volume=sum((m.taker_buy_base_volume for m in present), Decimal(0)),
                taker_buy_quote_volume=sum((m.taker_buy_quote_volume for m in present), Decimal(0)),
                taker_sell_base_volume=sum((m.taker_sell_base_volume for m in present), Decimal(0)),
                taker_sell_quote_volume=sum((m.taker_sell_quote_volume for m in present), Decimal(0)),
            ))
        else:
            out.append(HtfBar(
                open_time_ms=bucket,
                bar_end_exclusive_ms=bar_end,
                available_at_ms=bar_end,
                is_complete=False,
                expected_constituents=minutes,
                observed_constituents=len(present),
                open=None, high=None, low=None, close=None,
                base_volume=None, quote_volume=None, trade_count=None,
                taker_buy_base_volume=None, taker_buy_quote_volume=None,
                taker_sell_base_volume=None, taker_sell_quote_volume=None,
            ))
        bucket += step
    return out


def htf_to_parquet_bytes(rows: list[HtfBar]) -> bytes:
    import pyarrow as pa
    import pyarrow.parquet as pq

    def opt_str(values: list[Optional[Decimal]]) -> list[Optional[str]]:
        return [None if v is None else _dec_str(v) for v in values]

    arrays = {
        "open_time_ms": pa.array([r.open_time_ms for r in rows], type=pa.int64()),
        "bar_end_exclusive_ms": pa.array([r.bar_end_exclusive_ms for r in rows], type=pa.int64()),
        "available_at_ms": pa.array([r.available_at_ms for r in rows], type=pa.int64()),
        "is_complete": pa.array([r.is_complete for r in rows], type=pa.bool_()),
        "expected_constituents": pa.array([r.expected_constituents for r in rows], type=pa.int32()),
        "observed_constituents": pa.array([r.observed_constituents for r in rows], type=pa.int32()),
        "trade_count": pa.array([r.trade_count for r in rows], type=pa.int64()),
    }
    for name in DECIMAL_FIELDS:
        arrays[name] = pa.array(opt_str([getattr(r, name) for r in rows]), type=pa.string())
    buf = pa.BufferOutputStream()
    pq.write_table(pa.table(arrays), buf, compression="zstd")
    return buf.getvalue().to_pybytes()


def htf_from_parquet(path: Path) -> list[HtfBar]:
    import pyarrow.parquet as pq

    table = pq.read_table(path)
    cols = {name: table.column(name).to_pylist() for name in table.column_names}

    def dec(v):
        return None if v is None else Decimal(v)

    out = []
    for i in range(table.num_rows):
        out.append(HtfBar(
            open_time_ms=int(cols["open_time_ms"][i]),
            bar_end_exclusive_ms=int(cols["bar_end_exclusive_ms"][i]),
            available_at_ms=int(cols["available_at_ms"][i]),
            is_complete=bool(cols["is_complete"][i]),
            expected_constituents=int(cols["expected_constituents"][i]),
            observed_constituents=int(cols["observed_constituents"][i]),
            open=dec(cols["open"][i]),
            high=dec(cols["high"][i]),
            low=dec(cols["low"][i]),
            close=dec(cols["close"][i]),
            base_volume=dec(cols["base_volume"][i]),
            quote_volume=dec(cols["quote_volume"][i]),
            trade_count=None if cols["trade_count"][i] is None else int(cols["trade_count"][i]),
            taker_buy_base_volume=dec(cols["taker_buy_base_volume"][i]),
            taker_buy_quote_volume=dec(cols["taker_buy_quote_volume"][i]),
            taker_sell_base_volume=dec(cols["taker_sell_base_volume"][i]),
            taker_sell_quote_volume=dec(cols["taker_sell_quote_volume"][i]),
        ))
    return out


def bars_available_at_1m(bars: list[CanonicalBar], decision_time_ms: int) -> list[CanonicalBar]:
    """No-lookahead: a 1m bar is eligible only when available_at <= T.
    available_at is bar_end_exclusive = open_time + 60s, never close_time."""
    return [b for b in bars if b.available_at_ms <= decision_time_ms]


def bars_available_at_htf(bars: list[HtfBar], decision_time_ms: int) -> list[HtfBar]:
    return [b for b in bars if b.is_complete and b.available_at_ms <= decision_time_ms]


def sha256_of_canonical_identity_payload(payload: dict) -> str:
    return hashlib.sha256(dumps_deterministic(payload).encode("utf-8")).hexdigest()


def file_sha256_if_exists(path: Path) -> Optional[str]:
    return sha256_of_file(path) if path.exists() else None


def contract_file_sha256(repo_root: Path) -> str:
    path = repo_root / CONTRACT_PATH
    if not path.exists():
        return "UNKNOWN"
    return sha256_of_file(path)


def build_snapshot_identity(
    *,
    objects: list[SourceObject],
    inventory: list[dict],
    quality_report_sha256: str,
    output_checksums: dict[str, Optional[str]],
    contract_sha256: str,
    git_commit_sha: str,
) -> dict:
    source_identities = []
    for rec in inventory:
        source_identities.append({
            "source_period": rec.get("source_period"),
            "archive_class": rec.get("archive_class"),
            "source_url": rec.get("source_url"),
            "local_sha256": rec.get("local_sha256"),
            "expected_sha256": rec.get("expected_sha256"),
            "checksum_verification": rec.get("checksum_verification"),
            "byte_size": rec.get("byte_size"),
        })
    source_identities.sort(key=lambda r: (r["archive_class"], r["source_period"] or ""))
    payload = {
        "dataset_id": DATASET_ID,
        "contract_path": CONTRACT_PATH,
        "contract_sha256": contract_sha256,
        "start_inclusive": FROZEN_START_INCLUSIVE.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "end_exclusive": FROZEN_END_EXCLUSIVE.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "materializer_version": MATERIALIZER_VERSION,
        "canonicalization_version": CANONICALIZATION_VERSION,
        "aggregation_version": AGGREGATION_VERSION,
        "source_object_identities": source_identities,
        "quality_report_sha256": quality_report_sha256,
        "output_checksums": output_checksums,
        "provenance_git_commit_sha": git_commit_sha,
    }
    snapshot_id = sha256_of_canonical_identity_payload(payload)
    return {"snapshot_id": snapshot_id, "identity_payload": payload}


def remaining_extracted_csvs(root: Path) -> list[str]:
    found = []
    for dirpath, _dn, filenames in os.walk(root):
        for name in filenames:
            if name.lower().endswith(".csv"):
                found.append(str(Path(dirpath) / name))
    return found


def candidate_manifest(
    snapshot: dict, continuity: dict, inventory: list[dict], git_commit_sha: str,
) -> dict:
    verified = sum(1 for r in inventory if r.get("checksum_verification") == "VERIFIED")
    return {
        "dataset_id": DATASET_ID,
        "manifest_version": 0,
        "status": "MATERIALIZED_UNVERIFIED",
        "research_authorized": False,
        "contract_path": CONTRACT_PATH,
        "repo_planning_manifest": REPO_MANIFEST_PATH,
        "repo_planning_manifest_must_remain": {
            "status": "PLANNED_NOT_MATERIALIZED",
            "research_authorized": False,
            "current_state": "PLANNED_NOT_MATERIALIZED",
        },
        "snapshot_id": snapshot["snapshot_id"],
        "provenance_git_commit_sha": git_commit_sha,
        "materializer_version": MATERIALIZER_VERSION,
        "source_objects_verified": verified,
        "source_objects_planned": len(inventory),
        "expected_1m_rows": continuity.get("expected_minute_count"),
        "observed_unique_open_times": continuity.get("observed_unique_timestamps"),
        "missing_minutes": continuity.get("missing_minute_count"),
        "promotion": {
            "current_state": "MATERIALIZED_UNVERIFIED",
            "discovery_gate_passed": False,
            "confirmatory_gate_passed": False,
            "note": (
                "Candidate artifact only. Do not copy these values into "
                f"{REPO_MANIFEST_PATH} until a later human acceptance step."
            ),
        },
    }


def quality_report_markdown(quality: dict) -> str:
    c = quality.get("continuity", {})
    snap = quality.get("snapshot_id")
    gaps = c.get("missing_minute_count")
    return "\n".join([
        "# CORE_BTC_BINANCE_V0 quality report (generated)",
        "",
        f"snapshot_id: `{snap}`",
        f"source objects planned: {quality.get('source_objects_planned')}",
        f"source objects verified: {quality.get('source_objects_verified')}",
        f"checksum failures: {quality.get('checksum_failures')}",
        f"first observed: {c.get('first_observed_open_time_ms')}",
        f"last observed: {c.get('last_observed_open_time_ms')}",
        f"expected 1m minutes: {c.get('expected_minute_count')}",
        f"observed unique: {c.get('observed_unique_timestamps')}",
        f"missing minutes: {gaps}",
        f"duplicate extra rows: {c.get('duplicate_minute_count')}",
        f"conflicting duplicates: {quality.get('conflicting_duplicate_count')}",
        f"rejected schema rows: {quality.get('rejected_schema')}",
        f"rejected invariant rows: {quality.get('rejected_invariant')}",
        f"HTF incomplete buckets: {json.dumps(quality.get('htf_incomplete', {}), sort_keys=True)}",
        f"raw bytes: {quality.get('retained_raw_bytes')}",
        f"canonical bytes: {quality.get('materialized_bytes')}",
        f"extracted CSV leftovers: {quality.get('extracted_csv_leftovers')}",
        "",
        "Discovery acceptance gates are NOT automatically satisfied by this report.",
        "The repository planning manifest remains unpromoted.",
        "",
    ]) + "\n"
