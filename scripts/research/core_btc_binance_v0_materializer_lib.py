"""Deterministic CORE_BTC_BINANCE_V0 materialization helpers.

Network-free except where the caller injects a fetch function. Reuses the
hardened PR #71 checksum / ZIP-member / CSV / invariant machinery in
`core_btc_binance_v0_probe_lib`. Does not promote
`docs/manifests/CORE_BTC_BINANCE_V0.yaml`.

Remediation (RT-M01..M11): re-hash at canonical admission, partition
provenance, streaming continuity/HTF (no full-range Python bar lists),
fail-closed stage graph, disk-safety, quality-report file hashing, sidecar
pair adoption, exclusive dataset lock.
"""
from __future__ import annotations

import fcntl
import hashlib
import json
import os
import shutil
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Callable, Iterable, Iterator, Optional

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
MATERIALIZER_VERSION = 3
CANONICALIZATION_VERSION = 2
AGGREGATION_VERSION = 2
REPORT_SCHEMA_VERSION = 2
PARTITION_PROVENANCE_VERSION = 2
CANONICAL_SCHEMA_VERSION = 2
TOOL_KIND = "CORE_BTC_BINANCE_V0_MATERIALIZER"
LOCK_FILENAME = ".core_btc_binance_v0.lock"
RESEARCH_REQUIREMENTS_FILE = "requirements-research.txt"

FROZEN_START_INCLUSIVE = datetime(2020, 1, 1, tzinfo=UTC)
FROZEN_END_EXCLUSIVE = datetime(2026, 8, 26, tzinfo=UTC)
MONTHLY_START = "2020-01"
MONTHLY_END = "2026-07"
DAILY_START = "2026-08-01"
DAILY_END = "2026-08-25"

DEFAULT_DISK_RESERVE_BYTES = 5 * 1024 * 1024 * 1024
CONSERVATIVE_MONTHLY_ZIP_BYTES = 8 * 1024 * 1024
CONSERVATIVE_DAILY_ZIP_BYTES = 256 * 1024
CHECKSUM_BYTES_ESTIMATE = 128
CONSERVATIVE_CANONICAL_1M_TOTAL_BYTES = 512 * 1024 * 1024
CONSERVATIVE_HTF_TOTAL_BYTES = 256 * 1024 * 1024
CONSERVATIVE_PARTITION_PARQUET_BYTES = 16 * 1024 * 1024
ARROW_BATCH_ROWS = 8192
HTF_WRITE_BATCH_ROWS = 4096
STREAM_BATCH_ROWS = 16384
PARQUET_WRITE_KWARGS = {
    "compression": "zstd",
    "use_dictionary": False,
    "write_statistics": False,
    "store_schema": False,
}

GAP_EXTREME_PERCENTILE = 99

DECIMAL_STRING_POLICY = (
    "Price/volume columns are NUMERIC DECIMAL VALUES STORED AS CANONICAL "
    "DECIMAL STRINGS. Research code MUST parse/cast them numerically before "
    "comparison, sorting, arithmetic, or aggregation. Never compare them "
    "lexicographically. Normalization is format(Decimal(value), 'f'). "
    "Decimal('1.0') and Decimal('1.00') are distinct canonical text."
)

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

CANONICAL_1M_COLUMNS = (
    "open_time_ms", "bar_end_exclusive_ms", "available_at_ms", "close_time_ms",
    "trade_count", "source_period", "archive_class",
) + DECIMAL_FIELDS

# Semantic content digest: length-prefixed UTF-8 fields, uint32be length,
# rows in ascending open_time_ms. Integers as ASCII decimal; prices/volumes
# as format(Decimal, "f"). Path/parquet-metadata/provenance are excluded.
CANONICAL_CONTENT_FIELDS = (
    "open_time_ms", "bar_end_exclusive_ms", "available_at_ms", "close_time_ms",
    "open", "high", "low", "close",
    "base_volume", "quote_volume", "trade_count",
    "taker_buy_base_volume", "taker_buy_quote_volume",
    "taker_sell_base_volume", "taker_sell_quote_volume",
)
CANONICAL_CONTENT_DIGEST_VERSION = 1
ACQUIRE_SUCCESS_DISPOSITIONS = frozenset({"NEW", "REUSED_IDENTICAL"})
CONTENT_DIGEST_ENCODING = (
    "length-prefixed-utf8-uint32be; fields="
    + ",".join(CANONICAL_CONTENT_FIELDS)
    + "; decimals=format(Decimal,'f'); ints=ascii; row-order=ascending-open_time_ms"
)

PYARROW_REQUIRED_MESSAGE = (
    "pyarrow is required for CORE_BTC_BINANCE_V0 parquet I/O. "
    "Install the research extra with: pip install -r "
    f"{RESEARCH_REQUIREMENTS_FILE}  (pins pyarrow==17.0.0). "
    "CI/dev may instead use requirements-dev.txt, which layers the same pin. "
    "Do not add pyarrow to production requirements.txt."
)


class CoreBtcBinanceV0MaterializerError(ValueError):
    """Malformed materializer inputs or fail-closed disk/revision errors."""


class StaleCanonicalPartition(CoreBtcBinanceV0MaterializerError):
    """Canonical parquet was produced from a different raw revision."""


class StagePreconditionError(CoreBtcBinanceV0MaterializerError):
    """A pipeline stage was invoked without required prior evidence."""


# ---------------------------------------------------------------------------
# pyarrow
# ---------------------------------------------------------------------------
def require_pyarrow():
    """Fail clearly when the research parquet dependency is missing."""
    try:
        import pyarrow  # noqa: F401
        import pyarrow.parquet  # noqa: F401
    except ImportError as exc:
        raise CoreBtcBinanceV0MaterializerError(PYARROW_REQUIRED_MESSAGE) from exc
    return True


def _dec_str(value: Decimal) -> str:
    """Frozen textual normalization: format(Decimal, 'f')."""
    return format(value, "f")


class CanonicalContentHasher:
    """Incremental SHA-256 of canonical 1m row content. One row/batch at a time."""

    def __init__(self):
        self._h = hashlib.sha256()
        self.rows = 0
        self.first_open_time_ms: Optional[int] = None
        self.last_open_time_ms: Optional[int] = None

    def add_text(self, text: str) -> None:
        payload = text.encode("utf-8")
        self._h.update(len(payload).to_bytes(4, "big"))
        self._h.update(payload)

    def add_bar(self, bar: "CanonicalBar") -> None:
        self.add_text(str(int(bar.open_time_ms)))
        self.add_text(str(int(bar.bar_end_exclusive_ms)))
        self.add_text(str(int(bar.available_at_ms)))
        self.add_text(str(int(bar.close_time_ms)))
        self.add_text(_dec_str(bar.open))
        self.add_text(_dec_str(bar.high))
        self.add_text(_dec_str(bar.low))
        self.add_text(_dec_str(bar.close))
        self.add_text(_dec_str(bar.base_volume))
        self.add_text(_dec_str(bar.quote_volume))
        self.add_text(str(int(bar.trade_count)))
        self.add_text(_dec_str(bar.taker_buy_base_volume))
        self.add_text(_dec_str(bar.taker_buy_quote_volume))
        self.add_text(_dec_str(bar.taker_sell_base_volume))
        self.add_text(_dec_str(bar.taker_sell_quote_volume))
        t = int(bar.open_time_ms)
        if self.first_open_time_ms is None:
            self.first_open_time_ms = t
        self.last_open_time_ms = t
        self.rows += 1

    def add_parquet_cells(self, cells: dict) -> None:
        self.add_text(str(int(cells["open_time_ms"])))
        self.add_text(str(int(cells["bar_end_exclusive_ms"])))
        self.add_text(str(int(cells["available_at_ms"])))
        self.add_text(str(int(cells["close_time_ms"])))
        for name in (
            "open", "high", "low", "close", "base_volume", "quote_volume",
        ):
            self.add_text(str(cells[name]))
        self.add_text(str(int(cells["trade_count"])))
        for name in (
            "taker_buy_base_volume", "taker_buy_quote_volume",
            "taker_sell_base_volume", "taker_sell_quote_volume",
        ):
            self.add_text(str(cells[name]))
        t = int(cells["open_time_ms"])
        if self.first_open_time_ms is None:
            self.first_open_time_ms = t
        self.last_open_time_ms = t
        self.rows += 1

    def hexdigest(self) -> str:
        return self._h.hexdigest()


def canonical_content_sha256_from_bars(bars: Iterable["CanonicalBar"]) -> dict:
    hasher = CanonicalContentHasher()
    prev: Optional[int] = None
    for bar in bars:
        t = int(bar.open_time_ms)
        if prev is not None and t <= prev:
            raise CoreBtcBinanceV0MaterializerError(
                f"canonical content digest requires strictly increasing open_time_ms; saw {t} after {prev}"
            )
        hasher.add_bar(bar)
        prev = t
    return {
        "canonical_content_sha256": hasher.hexdigest(),
        "row_count": hasher.rows,
        "first_open_time_ms": hasher.first_open_time_ms,
        "last_open_time_ms": hasher.last_open_time_ms,
    }


def canonical_content_sha256_from_parquet(
    path: Path, batch_size: int = STREAM_BATCH_ROWS,
) -> dict:
    """Stream parquet row content. Does not load the partition as CanonicalBar."""
    require_pyarrow()
    import pyarrow.parquet as pq

    hasher = CanonicalContentHasher()
    prev: Optional[int] = None
    pf = pq.ParquetFile(path)
    cols = list(CANONICAL_CONTENT_FIELDS)
    for batch in pf.iter_batches(columns=cols, batch_size=batch_size):
        n = batch.num_rows
        arrays = {name: batch.column(name).to_pylist() for name in cols}
        for i in range(n):
            t = int(arrays["open_time_ms"][i])
            if prev is not None and t <= prev:
                raise CoreBtcBinanceV0MaterializerError(
                    f"canonical parquet is not strictly ordered at {path}: {t} after {prev}"
                )
            hasher.add_parquet_cells({name: arrays[name][i] for name in cols})
            prev = t
    return {
        "canonical_content_sha256": hasher.hexdigest(),
        "row_count": hasher.rows,
        "first_open_time_ms": hasher.first_open_time_ms,
        "last_open_time_ms": hasher.last_open_time_ms,
    }


# ---------------------------------------------------------------------------
# frozen source plan
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class SourceObject:
    archive_class: str
    source_period: str
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
    objects: list[SourceObject] = []
    for ym in _iter_year_months(MONTHLY_START, MONTHLY_END):
        zip_url = (
            f"{ARCHIVE_ROOT_MONTHLY}/{SYMBOL}/{INTERVAL}/{local_zip_filename(ym)}"
        )
        checksum_url = (
            f"{ARCHIVE_ROOT_MONTHLY}/{SYMBOL}/{INTERVAL}/{local_checksum_filename(ym)}"
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


def planned_source_object_count() -> int:
    return len(build_frozen_source_plan())


# ---------------------------------------------------------------------------
# dataset layout / io
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


def canonical_1m_provenance_path(root: Path, obj: SourceObject) -> Path:
    return canonical_1m_path(root, obj).with_suffix(".provenance.json")


def htf_path(root: Path, interval: str) -> Path:
    return dataset_layout(root)["canonical_htf"] / interval / "bars.parquet"


def atomic_write_bytes(path: Path, data: bytes) -> None:
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


@contextmanager
def dataset_lock(root: Path):
    """Exclusive flock for mutation stages. Released on process death."""
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    lock_path = root / LOCK_FILENAME
    fh = open(lock_path, "a+")
    try:
        try:
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise CoreBtcBinanceV0MaterializerError(
                f"dataset root is locked by another writer: {lock_path}"
            ) from exc
        fh.seek(0)
        fh.truncate()
        fh.write(str(os.getpid()))
        fh.flush()
        yield lock_path
    finally:
        try:
            fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
        except OSError:
            pass
        fh.close()


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
        "canonicalization_version": CANONICALIZATION_VERSION,
        "aggregation_version": AGGREGATION_VERSION,
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
        "decimal_string_policy": DECIMAL_STRING_POLICY,
        "objects": [o.as_plan_dict() for o in objects],
        "acceptance_note": (
            "This plan is not acquisition and not dataset acceptance. "
            f"{REPO_MANIFEST_PATH} stays PLANNED_NOT_MATERIALIZED / "
            "research_authorized: false until a later deliberate promotion."
        ),
    }


def estimate_object_bytes(archive_class: str, content_length: Optional[int]) -> tuple[int, str]:
    """HEAD Content-Length missing/0/invalid is UNKNOWN, never zero bytes."""
    if content_length is None or content_length <= 0:
        if archive_class == "monthly":
            return CONSERVATIVE_MONTHLY_ZIP_BYTES, "CONSERVATIVE_DEFAULT_MONTHLY"
        return CONSERVATIVE_DAILY_ZIP_BYTES, "CONSERVATIVE_DEFAULT_DAILY"
    return content_length, "HEAD_CONTENT_LENGTH"


def disk_usage_for(path: Path) -> dict:
    path.mkdir(parents=True, exist_ok=True)
    usage = shutil.disk_usage(path)
    return {
        "path": str(path),
        "total_bytes": usage.total,
        "used_bytes": usage.used,
        "free_bytes": usage.free,
    }


def _walk_size(path: Path, predicate) -> int:
    if not path.exists():
        return 0
    total = 0
    for dirpath, _dn, filenames in os.walk(path):
        for name in filenames:
            if predicate(name):
                total += (Path(dirpath) / name).stat().st_size
    return total


def retained_raw_size(root: Path) -> int:
    return _walk_size(
        dataset_layout(root)["raw"],
        lambda name: not (name.endswith(".part") or name.endswith(".tmp")),
    )


def part_files_size(root: Path) -> int:
    return _walk_size(
        Path(root),
        lambda name: name.endswith(".part") or name.endswith(".tmp") or ".part." in name,
    )


def materialized_size(root: Path) -> int:
    return _walk_size(dataset_layout(root)["canonical"], lambda _name: True)


def assert_disk_budget(
    root: Path,
    estimated_download_bytes: int,
    disk_reserve_bytes: int = DEFAULT_DISK_RESERVE_BYTES,
    extra_temp_bytes: Optional[int] = None,
    allow_zero_reserve: bool = False,
) -> dict:
    if disk_reserve_bytes <= 0 and not allow_zero_reserve:
        raise CoreBtcBinanceV0MaterializerError(
            "disk reserve must be positive unless --unsafe-no-disk-reserve is set"
        )
    usage = disk_usage_for(root)
    already = retained_raw_size(root)
    parts = part_files_size(root)
    remaining = max(0, estimated_download_bytes - already)
    already_canonical = materialized_size(root)
    canonical_need = max(0, CONSERVATIVE_CANONICAL_1M_TOTAL_BYTES - already_canonical)
    htf_need = CONSERVATIVE_HTF_TOTAL_BYTES
    temp_bound = extra_temp_bytes if extra_temp_bytes is not None else (
        CONSERVATIVE_MONTHLY_ZIP_BYTES + CONSERVATIVE_PARTITION_PARQUET_BYTES
    )
    need = remaining + parts + canonical_need + htf_need + temp_bound + disk_reserve_bytes
    ok = usage["free_bytes"] >= need
    report = {
        **usage,
        "estimated_raw_download_bytes": estimated_download_bytes,
        "retained_raw_bytes": already,
        "part_and_tmp_bytes": parts,
        "remaining_download_bytes": remaining,
        "canonical_output_estimate_bytes": canonical_need,
        "htf_output_estimate_bytes": htf_need,
        "temp_bound_bytes": temp_bound,
        "disk_reserve_bytes": disk_reserve_bytes,
        "bytes_required_including_reserve": need,
        "disk_safety_ok": ok,
    }
    if not ok:
        raise CoreBtcBinanceV0MaterializerError(
            "disk-safety gate failed: "
            f"free={usage['free_bytes']} required={need} "
            f"(remaining_download={remaining} + parts={parts} + "
            f"canonical={canonical_need} + htf={htf_need} + "
            f"temp={temp_bound} + reserve={disk_reserve_bytes})"
        )
    return report


# ---------------------------------------------------------------------------
# acquire (atomic ZIP+CHECKSUM pair)
# ---------------------------------------------------------------------------
FetchFn = Callable[[str], tuple[Optional[bytes], str, Optional[int]]]


def _on_disk_checksum_verification(root: Path, obj: SourceObject) -> dict:
    zip_path = raw_zip_path(root, obj)
    checksum_path = raw_checksum_path(root, obj)
    out = {
        "local_sha256": None,
        "expected_sha256": None,
        "checksum_observed_filename": None,
        "checksum_verification": "NOT_ATTEMPTED",
        "byte_size": None,
    }
    if not zip_path.exists() or not checksum_path.exists():
        out["checksum_verification"] = "NOT_VERIFIABLE_MISSING_CHECKSUM"
        if zip_path.exists():
            out["local_sha256"] = sha256_of_file(zip_path)
            out["byte_size"] = zip_path.stat().st_size
        return out
    out["local_sha256"] = sha256_of_file(zip_path)
    out["byte_size"] = zip_path.stat().st_size
    try:
        parsed = parse_checksum_text(checksum_path.read_text(encoding="utf-8"))
    except CoreBtcBinanceV0ProbeError:
        out["checksum_verification"] = "NOT_VERIFIABLE_MISSING_CHECKSUM"
        return out
    out["expected_sha256"] = parsed["sha256"]
    out["checksum_observed_filename"] = parsed["filename"]
    out["checksum_verification"] = evaluate_checksum_verification(
        out["local_sha256"], parsed, obj.expected_zip_filename)
    return out


def _adopt_zip_and_checksum(zip_path: Path, checksum_path: Path, zip_bytes: bytes, checksum_bytes: bytes) -> None:
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    part_zip = zip_path.with_suffix(zip_path.suffix + ".part")
    part_sum = checksum_path.with_suffix(checksum_path.suffix + ".part")
    try:
        atomic_write_bytes(part_zip, zip_bytes)
        atomic_write_bytes(part_sum, checksum_bytes)
        os.replace(part_zip, zip_path)
        os.replace(part_sum, checksum_path)
    finally:
        for p in (part_zip, part_sum):
            if p.exists():
                try:
                    p.unlink()
                except OSError:
                    pass


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
    remote_sha = parsed["sha256"] if parsed is not None else None
    disposition = decide_existing_zip_disposition(existing_sha, remote_sha)
    record["disposition"] = disposition

    if disposition == "REVISION_CONFLICT":
        record["source_status"] = "REVISION_CONFLICT"
        disk = _on_disk_checksum_verification(root, obj)
        record.update({k: disk[k] for k in (
            "local_sha256", "byte_size", "checksum_verification",
            "checksum_observed_filename") if disk.get(k) is not None or k == "checksum_verification"})
        record["local_sha256"] = existing_sha
        record["byte_size"] = zip_path.stat().st_size
        record["checksum_verification"] = disk["checksum_verification"]
        return record

    if disposition == "REUSED_UNVERIFIED_NO_REFERENCE":
        record["source_status"] = disposition
        disk = _on_disk_checksum_verification(root, obj)
        record["local_sha256"] = existing_sha
        record["byte_size"] = zip_path.stat().st_size
        record["checksum_verification"] = disk["checksum_verification"]
        return record

    if disposition == "REUSED_IDENTICAL":
        # ZIP matches remote digest. Adopt sidecar only when missing or already
        # identical; never report VERIFIED unless on-disk pair matches.
        if checksum_bytes is not None and parsed is not None:
            if not checksum_path.exists():
                atomic_write_bytes(checksum_path, checksum_bytes)
            else:
                try:
                    on_disk = parse_checksum_text(checksum_path.read_text(encoding="utf-8"))
                except CoreBtcBinanceV0ProbeError:
                    on_disk = None
                if on_disk is None or on_disk["sha256"] != existing_sha:
                    record["source_status"] = "SIDECAR_ZIP_INCONSISTENT"
                    record["disposition"] = "SIDECAR_ZIP_INCONSISTENT"
                    record["local_sha256"] = existing_sha
                    record["byte_size"] = zip_path.stat().st_size
                    record["checksum_verification"] = "MISMATCH"
                    return record
        disk = _on_disk_checksum_verification(root, obj)
        record["source_status"] = "REUSED_IDENTICAL"
        record["local_sha256"] = disk["local_sha256"]
        record["byte_size"] = disk["byte_size"]
        record["checksum_verification"] = disk["checksum_verification"]
        record["checksum_observed_filename"] = disk["checksum_observed_filename"]
        return record

    # NEW: no ZIP on disk.
    if checksum_path.exists():
        try:
            old_side = parse_checksum_text(checksum_path.read_text(encoding="utf-8"))
        except CoreBtcBinanceV0ProbeError:
            old_side = None
        if parsed is None or old_side is None or old_side["sha256"] != parsed["sha256"]:
            record["source_status"] = "REVISION_CONFLICT"
            record["disposition"] = "REVISION_CONFLICT"
            record["checksum_verification"] = "NOT_VERIFIABLE_MISSING_CHECKSUM"
            return record

    if parsed is None or checksum_bytes is None:
        record["source_status"] = checksum_status
        record["checksum_verification"] = "NOT_VERIFIABLE_MISSING_CHECKSUM"
        return record

    zip_bytes, zip_status, _cl = fetch(obj.source_url)
    if zip_bytes is None:
        record["source_status"] = zip_status
        return record

    local = sha256_of_bytes(zip_bytes)
    pair_status = evaluate_checksum_verification(local, parsed, obj.expected_zip_filename)
    if pair_status != "VERIFIED":
        record["source_status"] = zip_status
        record["local_sha256"] = local
        record["byte_size"] = len(zip_bytes)
        record["checksum_verification"] = pair_status
        return record

    _adopt_zip_and_checksum(zip_path, checksum_path, zip_bytes, checksum_bytes)
    disk = _on_disk_checksum_verification(root, obj)
    record["source_status"] = "HTTP_200"
    record["disposition"] = "NEW"
    record["local_sha256"] = disk["local_sha256"]
    record["byte_size"] = disk["byte_size"]
    record["checksum_verification"] = disk["checksum_verification"]
    record["checksum_observed_filename"] = disk["checksum_observed_filename"]
    record["expected_sha256"] = disk["expected_sha256"]
    return record


def acquire_record_is_success(record: dict) -> bool:
    """RT-M12: success is only NEW/REUSED_IDENTICAL + currently VERIFIED."""
    if record.get("disposition") not in ACQUIRE_SUCCESS_DISPOSITIONS:
        return False
    if record.get("checksum_verification") != "VERIFIED":
        return False
    if record.get("source_status") in {
        "REVISION_CONFLICT", "SIDECAR_ZIP_INCONSISTENT",
    }:
        return False
    return True


def acquire_all_verified(records: list[dict], planned: int) -> bool:
    if len(records) != planned:
        return False
    if any(
        r.get("disposition") == "REVISION_CONFLICT"
        or r.get("source_status") == "REVISION_CONFLICT"
        for r in records
    ):
        return False
    return all(acquire_record_is_success(r) for r in records)


# ---------------------------------------------------------------------------
# audit-raw / materialize
# ---------------------------------------------------------------------------
@dataclass
class CanonicalBar:
    open_time_ms: int
    bar_end_exclusive_ms: int
    available_at_ms: int
    close_time_ms: int
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

    def semantic_tuple(self) -> tuple:
        return (
            self.open_time_ms, self.close_time_ms,
            self.open, self.high, self.low, self.close,
            self.base_volume, self.quote_volume, self.trade_count,
            self.taker_buy_base_volume, self.taker_buy_quote_volume,
        )


def kline_to_canonical(row, obj: SourceObject, source_sha256: str | None = None) -> CanonicalBar:
    """`source_sha256` is ignored (partition provenance holds source identity)."""
    del source_sha256
    bar_end = bar_end_exclusive_ms(row.open_time_ms)
    return CanonicalBar(
        open_time_ms=row.open_time_ms,
        bar_end_exclusive_ms=bar_end,
        available_at_ms=bar_end,
        close_time_ms=row.close_time_ms,
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
    )


def admit_kline_rows(rows, obj: SourceObject) -> tuple[list[CanonicalBar], dict]:
    """Admit klines for one source object. Holds at most this partition in memory."""
    global_start, global_end = frozen_range_ms()
    by_time: dict[int, CanonicalBar] = {}
    identical = 0
    conflicts: set[int] = set()
    rejected_invariant = 0
    rejected_identity = 0
    rejected_end = 0
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
        bar = kline_to_canonical(row, obj)
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
    return accepted, {
        "identical_duplicate_count": identical,
        "conflicting_duplicate_open_times": sorted(conflicts),
        "rejected_invariant": rejected_invariant,
        "rejected_identity": rejected_identity,
        "rejected_end_exclusive": rejected_end,
    }


def parse_admit_current_raw(root: Path, obj: SourceObject) -> tuple[list[CanonicalBar], dict]:
    zip_path = raw_zip_path(root, obj)
    csv_text, _names, status = read_kline_csv_member_named(zip_path, obj.expected_csv_member_name)
    if status != "OK" or csv_text is None:
        raise StagePreconditionError(
            f"cannot parse current raw ZIP for {obj.source_period}: {status}"
        )
    rows, _meta = parse_kline_csv(csv_text)
    return admit_kline_rows(rows, obj)


def audit_raw_object(root: Path, obj: SourceObject) -> dict:
    zip_path = raw_zip_path(root, obj)
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
    disk = _on_disk_checksum_verification(root, obj)
    record.update(disk)
    if not zip_path.exists():
        record["parser_status"] = "NO_SUCH_FILE"
        return record
    if record["checksum_verification"] != "VERIFIED":
        return record

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
    record["admitted_to_canonical"] = True
    return record


def audit_all_verified(records: list[dict], planned: int) -> bool:
    if len(records) != planned:
        return False
    return all(
        r.get("checksum_verification") == "VERIFIED" and r.get("parser_status") == "OK"
        for r in records
    )


def canonical_rows_to_parquet_bytes(rows: list[CanonicalBar]) -> bytes:
    require_pyarrow()
    import pyarrow as pa
    import pyarrow.parquet as pq

    rows_sorted = sorted(rows, key=lambda r: r.open_time_ms)
    arrays = {
        "open_time_ms": pa.array([r.open_time_ms for r in rows_sorted], type=pa.int64()),
        "bar_end_exclusive_ms": pa.array([r.bar_end_exclusive_ms for r in rows_sorted], type=pa.int64()),
        "available_at_ms": pa.array([r.available_at_ms for r in rows_sorted], type=pa.int64()),
        "close_time_ms": pa.array([r.close_time_ms for r in rows_sorted], type=pa.int64()),
        "trade_count": pa.array([r.trade_count for r in rows_sorted], type=pa.int64()),
        "source_period": pa.array([r.source_period for r in rows_sorted], type=pa.string()),
        "archive_class": pa.array([r.archive_class for r in rows_sorted], type=pa.string()),
    }
    for name in DECIMAL_FIELDS:
        arrays[name] = pa.array([_dec_str(getattr(r, name)) for r in rows_sorted], type=pa.string())
    buf = pa.BufferOutputStream()
    pq.write_table(pa.table(arrays), buf, **PARQUET_WRITE_KWARGS)
    return buf.getvalue().to_pybytes()


def canonical_rows_from_parquet(path: Path) -> list[CanonicalBar]:
    """Test/helper reader for one partition. Production scans use iter_batches."""
    require_pyarrow()
    import pyarrow.parquet as pq

    table = pq.read_table(path)
    cols = {name: table.column(name).to_pylist() for name in table.column_names}
    n = table.num_rows
    out = []
    for i in range(n):
        close_time = cols["close_time_ms"][i] if "close_time_ms" in cols else (
            int(cols["open_time_ms"][i]) + BAR_MS - 1)
        out.append(CanonicalBar(
            open_time_ms=int(cols["open_time_ms"][i]),
            bar_end_exclusive_ms=int(cols["bar_end_exclusive_ms"][i]),
            available_at_ms=int(cols["available_at_ms"][i]),
            close_time_ms=int(close_time),
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
        ))
    return out


def _partition_provenance_payload(
    obj: SourceObject, raw: dict, parquet_sha: str, content: dict, extra: dict,
) -> dict:
    return {
        "schema_version": PARTITION_PROVENANCE_VERSION,
        "dataset_id": DATASET_ID,
        "source_period": obj.source_period,
        "archive_class": obj.archive_class,
        "source_url": obj.source_url,
        "expected_zip_filename": obj.expected_zip_filename,
        "expected_csv_member_name": obj.expected_csv_member_name,
        "source_local_sha256": raw["local_sha256"],
        "source_expected_sha256": raw["expected_sha256"],
        "checksum_verification": raw["checksum_verification"],
        "materializer_version": MATERIALIZER_VERSION,
        "canonicalization_version": CANONICALIZATION_VERSION,
        "parser_version": CANONICALIZATION_VERSION,
        "canonical_schema_version": CANONICAL_SCHEMA_VERSION,
        "canonical_content_digest_version": CANONICAL_CONTENT_DIGEST_VERSION,
        "canonical_content_encoding": CONTENT_DIGEST_ENCODING,
        "decimal_string_policy": "format(Decimal(value), 'f')",
        "admitted_rows": content["row_count"],
        "row_count": content["row_count"],
        "first_open_time_ms": content["first_open_time_ms"],
        "last_open_time_ms": content["last_open_time_ms"],
        "canonical_content_sha256": content["canonical_content_sha256"],
        "canonical_parquet_sha256": parquet_sha,
        "parquet_sha256": parquet_sha,
        **extra,
    }


def materialize_object_1m(root: Path, obj: SourceObject, audit_record: dict) -> dict:
    """Parse CURRENT verified ZIP bytes into a canonical 1m parquet partition.

    RT-M01: re-hash ZIP + sidecar immediately before admission. A stale audit
    record cannot admit changed bytes.
    """
    require_pyarrow()
    result = {
        "source_period": obj.source_period,
        "archive_class": obj.archive_class,
        "canonical_path": None,
        "provenance_path": None,
        "admitted_rows": 0,
        "identical_duplicate_count": 0,
        "conflicting_duplicate_open_times": [],
        "rejected_schema": audit_record.get("malformed_row_count") or 0,
        "rejected_invariant": 0,
        "rejected_identity": 0,
        "rejected_end_exclusive": 0,
        "status": "NOT_ATTEMPTED",
    }
    zip_path = raw_zip_path(root, obj)
    disk = _on_disk_checksum_verification(root, obj)
    if disk["checksum_verification"] != "VERIFIED":
        result["status"] = "SKIPPED_NOT_VERIFIED"
        result["current_checksum_verification"] = disk["checksum_verification"]
        return result
    if audit_record.get("checksum_verification") != "VERIFIED":
        result["status"] = "STALE_AUDIT"
        return result
    if audit_record.get("local_sha256") != disk["local_sha256"]:
        result["status"] = "STALE_AUDIT"
        result["audit_sha256"] = audit_record.get("local_sha256")
        result["current_sha256"] = disk["local_sha256"]
        return result
    if audit_record.get("expected_sha256") not in (None, disk["expected_sha256"]):
        result["status"] = "STALE_AUDIT"
        return result
    if audit_record.get("parser_status") != "OK":
        result["status"] = "SKIPPED_PARSER"
        return result

    csv_text, _names, status = read_kline_csv_member_named(zip_path, obj.expected_csv_member_name)
    if status != "OK" or csv_text is None:
        result["status"] = "SKIPPED_PARSER"
        return result
    rows, _meta = parse_kline_csv(csv_text)
    accepted, stats = admit_kline_rows(rows, obj)
    identical = stats["identical_duplicate_count"]
    conflicts = stats["conflicting_duplicate_open_times"]
    rejected_invariant = stats["rejected_invariant"]
    rejected_identity = stats["rejected_identity"]
    rejected_end = stats["rejected_end_exclusive"]

    out_path = canonical_1m_path(root, obj)
    raw_content = canonical_content_sha256_from_bars(accepted)
    payload = canonical_rows_to_parquet_bytes(accepted)
    parquet_sha = sha256_of_bytes(payload)
    extra = {
        "identical_duplicate_count": identical,
        "conflicting_duplicate_open_times": list(conflicts),
        "rejected_invariant": rejected_invariant,
        "rejected_identity": rejected_identity,
        "rejected_end_exclusive": rejected_end,
        "rejected_schema": result["rejected_schema"],
    }
    result["canonical_path"] = str(out_path.relative_to(root)).replace("\\", "/")
    result["provenance_path"] = str(
        canonical_1m_provenance_path(root, obj).relative_to(root)).replace("\\", "/")
    result["admitted_rows"] = len(accepted)
    result["identical_duplicate_count"] = identical
    result["conflicting_duplicate_open_times"] = list(conflicts)
    result["rejected_invariant"] = rejected_invariant
    result["rejected_identity"] = rejected_identity
    result["rejected_end_exclusive"] = rejected_end
    result["source_local_sha256"] = disk["local_sha256"]
    result["canonical_parquet_sha256"] = parquet_sha
    result["canonical_content_sha256"] = raw_content["canonical_content_sha256"]

    existed_identical = out_path.exists() and sha256_of_file(out_path) == parquet_sha
    if not existed_identical:
        atomic_write_bytes(out_path, payload)
    parquet_content = canonical_content_sha256_from_parquet(out_path)
    if parquet_content["canonical_content_sha256"] != raw_content["canonical_content_sha256"]:
        result["status"] = "CONTENT_DIGEST_MISMATCH"
        result["raw_derived_canonical_content_sha256"] = raw_content["canonical_content_sha256"]
        result["parquet_canonical_content_sha256"] = parquet_content["canonical_content_sha256"]
        return result
    if sha256_of_file(out_path) != parquet_sha:
        result["status"] = "PARQUET_SHA_MISMATCH"
        return result
    provenance = _partition_provenance_payload(obj, disk, parquet_sha, raw_content, extra)
    write_json(canonical_1m_provenance_path(root, obj), provenance)
    result["status"] = "REUSED_IDENTICAL_PARTITION" if existed_identical else "WROTE"
    return result


def verify_canonical_partitions(root: Path, objects: list[SourceObject]) -> list[dict]:
    """RT-M02/M13: bind CURRENT raw ZIP semantics to CURRENT parquet content.

    Provenance JSON is metadata. The authority is:
    digest(admitted rows from current ZIP) == digest(parquet row content).
    """
    problems = []
    provenances = []
    for obj in objects:
        raw = _on_disk_checksum_verification(root, obj)
        parq = canonical_1m_path(root, obj)
        prov_path = canonical_1m_provenance_path(root, obj)
        if raw["checksum_verification"] != "VERIFIED":
            problems.append({
                "source_period": obj.source_period,
                "status": "RAW_NOT_VERIFIED",
                "checksum_verification": raw["checksum_verification"],
            })
            continue
        if not parq.exists() or not prov_path.exists():
            problems.append({"source_period": obj.source_period, "status": "MISSING_CANONICAL"})
            continue
        try:
            prov = json.loads(prov_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            problems.append({"source_period": obj.source_period, "status": "PROVENANCE_UNREADABLE"})
            continue
        actual_parquet_sha = sha256_of_file(parq)
        try:
            admitted, _stats = parse_admit_current_raw(root, obj)
            expected_content = canonical_content_sha256_from_bars(admitted)
            del admitted
            actual_content = canonical_content_sha256_from_parquet(parq)
        except (CoreBtcBinanceV0MaterializerError, StagePreconditionError) as exc:
            problems.append({
                "source_period": obj.source_period,
                "status": "CONTENT_DIGEST_ERROR",
                "error": str(exc)[:500],
            })
            continue
        if expected_content["canonical_content_sha256"] != actual_content["canonical_content_sha256"]:
            problems.append({
                "source_period": obj.source_period,
                "status": "STALE_CANONICAL_PARTITION",
                "reason": "RAW_PARQUET_CONTENT_DIGEST_MISMATCH",
                "raw_derived_canonical_content_sha256": expected_content["canonical_content_sha256"],
                "parquet_canonical_content_sha256": actual_content["canonical_content_sha256"],
            })
            continue
        checks = [
            (prov.get("parquet_sha256") or prov.get("canonical_parquet_sha256")) == actual_parquet_sha,
            prov.get("source_period") == obj.source_period,
            prov.get("archive_class") == obj.archive_class,
            prov.get("source_local_sha256") == raw["local_sha256"],
            prov.get("source_expected_sha256") == raw["expected_sha256"],
            (prov.get("row_count") if prov.get("row_count") is not None else prov.get("admitted_rows"))
            == actual_content["row_count"],
            prov.get("first_open_time_ms") == actual_content["first_open_time_ms"],
            prov.get("last_open_time_ms") == actual_content["last_open_time_ms"],
            prov.get("materializer_version") == MATERIALIZER_VERSION,
            prov.get("canonical_schema_version") == CANONICAL_SCHEMA_VERSION,
            (prov.get("parser_version") or prov.get("canonicalization_version")) == CANONICALIZATION_VERSION,
        ]
        if not all(checks):
            problems.append({
                "source_period": obj.source_period,
                "status": "STALE_CANONICAL_PARTITION",
                "reason": "PROVENANCE_METADATA_MISMATCH",
                "parquet_sha256_ok": checks[0],
                "source_period_ok": checks[1],
                "archive_class_ok": checks[2],
                "source_local_ok": checks[3],
                "source_expected_ok": checks[4],
                "row_count_ok": checks[5],
                "first_ok": checks[6],
                "last_ok": checks[7],
                "materializer_version_ok": checks[8],
                "schema_version_ok": checks[9],
                "parser_version_ok": checks[10],
            })
            continue
        provenances.append(prov)
    if problems:
        stale = any(p.get("status") == "STALE_CANONICAL_PARTITION" for p in problems)
        exc_cls = StaleCanonicalPartition if stale else StagePreconditionError
        raise exc_cls(
            dumps_deterministic({
                "error": "CANONICAL_PROVENANCE_FAILED",
                "problems": problems,
            })
        )
    if len(provenances) != len(objects):
        raise StagePreconditionError("canonical provenance count != planned objects")
    return provenances


def load_all_canonical_1m(root: Path, objects: list[SourceObject]) -> list[CanonicalBar]:
    """Small-fixture helper only. Production aggregate/finalize must not use this."""
    bars: list[CanonicalBar] = []
    for obj in objects:
        path = canonical_1m_path(root, obj)
        if path.exists():
            bars.extend(canonical_rows_from_parquet(path))
    bars.sort(key=lambda r: r.open_time_ms)
    return bars


def merge_cross_object(bars: list[CanonicalBar]) -> tuple[list[CanonicalBar], dict]:
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
# streaming readers (no full-dataset to_pylist)
# ---------------------------------------------------------------------------
def iter_canonical_batches(
    root: Path, objects: list[SourceObject], columns: Optional[list[str]] = None,
    batch_size: int = STREAM_BATCH_ROWS,
) -> Iterator:
    """Yield pyarrow RecordBatches in plan order. Never concatenates all partitions."""
    require_pyarrow()
    import pyarrow.parquet as pq

    for obj in objects:
        path = canonical_1m_path(root, obj)
        if not path.exists():
            continue
        pf = pq.ParquetFile(path)
        for batch in pf.iter_batches(columns=columns, batch_size=batch_size):
            yield batch


def iter_canonical_open_times(root: Path, objects: list[SourceObject]) -> Iterator[int]:
    for batch in iter_canonical_batches(root, objects, columns=["open_time_ms"]):
        for t in batch.column("open_time_ms").to_pylist():
            yield int(t)


# ---------------------------------------------------------------------------
# streaming continuity
# ---------------------------------------------------------------------------
def _add_missingness(start_ms: int, end_exclusive_ms: int, by_year: dict, by_month: dict) -> None:
    t = start_ms
    while t < end_exclusive_ms:
        dt = datetime.fromtimestamp(t / 1000, tz=UTC)
        year = f"{dt.year:04d}"
        month = f"{dt.year:04d}-{dt.month:02d}"
        month_end = month_bounds_ms(month)[1]
        chunk_end = min(month_end, end_exclusive_ms)
        minutes = (chunk_end - t) // BAR_MS
        by_year[year] = by_year.get(year, 0) + minutes
        by_month[month] = by_month.get(month, 0) + minutes
        t = chunk_end


def continuity_audit_from_times(
    times: Iterable[int],
    start_ms: Optional[int] = None,
    end_ms: Optional[int] = None,
) -> dict:
    """O(observed) continuity. No list(range(start, end, 60_000))."""
    if start_ms is None or end_ms is None:
        start_ms, end_ms = frozen_range_ms()
    expected_count = (end_ms - start_ms) // BAR_MS
    expected_next = start_ms
    observed = 0
    unique = 0
    duplicate_count = 0
    duplicate_times: list[int] = []
    extra: list[int] = []
    gaps: list[dict] = []
    longest = 0
    last_t: Optional[int] = None
    strictly = True
    by_year: dict[str, int] = {}
    by_month: dict[str, int] = {}
    first = None
    last_obs = None

    def emit_gap(gstart: int, gend: int) -> None:
        nonlocal longest
        if gend <= gstart:
            return
        minutes = (gend - gstart) // BAR_MS
        longest = max(longest, minutes)
        gaps.append({
            "start_ms": gstart,
            "end_exclusive_ms": gend,
            "missing_minutes": minutes,
        })
        _add_missingness(gstart, gend, by_year, by_month)

    for t in times:
        observed += 1
        t = int(t)
        if first is None:
            first = t
        if last_t is not None and t < last_t:
            strictly = False
        if t < start_ms or t >= end_ms:
            extra.append(t)
            last_t = t
            continue
        if last_t == t:
            duplicate_count += 1
            if not duplicate_times or duplicate_times[-1] != t:
                duplicate_times.append(t)
            last_t = t
            continue
        unique += 1
        if t < expected_next:
            strictly = False
            duplicate_count += 1
            duplicate_times.append(t)
            last_t = t
            continue
        if t > expected_next:
            emit_gap(expected_next, t)
        expected_next = t + BAR_MS
        last_t = t
        last_obs = t
    if expected_next < end_ms:
        emit_gap(expected_next, end_ms)

    missing = sum(g["missing_minutes"] for g in gaps)
    return {
        "start_inclusive_ms": start_ms,
        "end_exclusive_ms": end_ms,
        "expected_minute_count": expected_count,
        "observed_rows": observed,
        "observed_unique_timestamps": unique,
        "missing_minute_count": missing,
        "duplicate_minute_count": duplicate_count,
        "duplicate_open_times": duplicate_times,
        "rows_outside_frozen_range": extra,
        "longest_contiguous_gap_minutes": longest,
        "gaps": gaps,
        "missingness_by_year": {k: by_year[k] for k in sorted(by_year)},
        "missingness_by_month": {k: by_month[k] for k in sorted(by_month)},
        "first_observed_open_time_ms": first,
        "last_observed_open_time_ms": last_obs,
        "is_strictly_ordered": strictly,
    }


def continuity_audit(
    bars: Iterable,
    start_ms: Optional[int] = None,
    end_ms: Optional[int] = None,
) -> dict:
    def times():
        for b in bars:
            yield b.open_time_ms if hasattr(b, "open_time_ms") else int(b)
    return continuity_audit_from_times(times(), start_ms, end_ms)


def continuity_audit_from_root(root: Path, objects: list[SourceObject]) -> dict:
    start_ms, end_ms = frozen_range_ms()
    return continuity_audit_from_times(iter_canonical_open_times(root, objects), start_ms, end_ms)


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
    """In-memory diagnostic for small fixtures. Does not repair gaps."""
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


def gap_extreme_diagnostic_streaming(root: Path, objects: list[SourceObject], gaps: list[dict]) -> dict:
    """p99 via float64 sample of the population (diagnostic only; not admission)."""
    want = set()
    for gap in gaps:
        want.add(gap["start_ms"] - BAR_MS)
        want.add(gap["end_exclusive_ms"])
    abs_returns: list[float] = []
    volumes: list[float] = []
    adjacent: dict[int, tuple[float, float, float]] = {}
    cols = ["open_time_ms", "open", "close", "base_volume"]
    for batch in iter_canonical_batches(root, objects, columns=cols):
        times = batch.column("open_time_ms").to_pylist()
        opens = batch.column("open").to_pylist()
        closes = batch.column("close").to_pylist()
        vols = batch.column("base_volume").to_pylist()
        for t, o, c, v in zip(times, opens, closes, vols):
            t = int(t)
            of = float(o)
            cf = float(c)
            vf = float(v)
            if of > 0:
                abs_returns.append(abs(cf / of - 1.0))
            volumes.append(vf)
            if t in want:
                adjacent[t] = (of, cf, vf)
    abs_returns.sort()
    volumes.sort()
    p_ret = abs_returns[(GAP_EXTREME_PERCENTILE * len(abs_returns) + 99) // 100 - 1] if abs_returns else None
    p_vol = volumes[(GAP_EXTREME_PERCENTILE * len(volumes) + 99) // 100 - 1] if volumes else None
    if abs_returns:
        p_ret = abs_returns[min(max((GAP_EXTREME_PERCENTILE * len(abs_returns) + 99) // 100 - 1, 0), len(abs_returns) - 1)]
    if volumes:
        p_vol = volumes[min(max((GAP_EXTREME_PERCENTILE * len(volumes) + 99) // 100 - 1, 0), len(volumes) - 1)]
    flagged = []
    for gap in gaps:
        adj_times = [t for t in (gap["start_ms"] - BAR_MS, gap["end_exclusive_ms"]) if t in adjacent]
        extreme = False
        reasons = []
        for t in adj_times:
            of, cf, vf = adjacent[t]
            if of > 0 and p_ret is not None and abs(cf / of - 1.0) >= p_ret:
                extreme = True
                reasons.append("adjacent_abs_return_ge_p99")
            if p_vol is not None and vf >= p_vol:
                extreme = True
                reasons.append("adjacent_volume_ge_p99")
        flagged.append({
            **gap,
            "adjacent_open_time_ms": adj_times,
            "extreme_adjacent": extreme,
            "reasons": sorted(set(reasons)),
        })
    return {
        "rule": (
            f"An adjacent 1m bar is extreme when |close/open-1| or base_volume "
            f"is at or above the {GAP_EXTREME_PERCENTILE}th percentile of the "
            "observed canonical 1m population. Predeclared; not an edge rule; "
            "does not repair or drop gaps. Percentile uses float64 of the "
            "streamed population and never changes admission."
        ),
        "percentile": GAP_EXTREME_PERCENTILE,
        "p99_abs_return": None if p_ret is None else repr(p_ret),
        "p99_base_volume": None if p_vol is None else repr(p_vol),
        "gaps": flagged,
        "extreme_gap_count": sum(1 for g in flagged if g["extreme_adjacent"]),
    }


# ---------------------------------------------------------------------------
# HTF: in-memory (small tests) + streaming (production)
# ---------------------------------------------------------------------------
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


def _htf_complete(members: list[CanonicalBar], bucket: int, minutes: int, bar_end: int) -> HtfBar:
    return HtfBar(
        open_time_ms=bucket,
        bar_end_exclusive_ms=bar_end,
        available_at_ms=bar_end,
        is_complete=True,
        expected_constituents=minutes,
        observed_constituents=minutes,
        open=members[0].open,
        high=max(m.high for m in members),
        low=min(m.low for m in members),
        close=members[-1].close,
        base_volume=sum((m.base_volume for m in members), Decimal(0)),
        quote_volume=sum((m.quote_volume for m in members), Decimal(0)),
        trade_count=sum(m.trade_count for m in members),
        taker_buy_base_volume=sum((m.taker_buy_base_volume for m in members), Decimal(0)),
        taker_buy_quote_volume=sum((m.taker_buy_quote_volume for m in members), Decimal(0)),
        taker_sell_base_volume=sum((m.taker_sell_base_volume for m in members), Decimal(0)),
        taker_sell_quote_volume=sum((m.taker_sell_quote_volume for m in members), Decimal(0)),
    )


def _htf_incomplete(bucket: int, minutes: int, bar_end: int, observed: int) -> HtfBar:
    return HtfBar(
        open_time_ms=bucket,
        bar_end_exclusive_ms=bar_end,
        available_at_ms=bar_end,
        is_complete=False,
        expected_constituents=minutes,
        observed_constituents=observed,
        open=None, high=None, low=None, close=None,
        base_volume=None, quote_volume=None, trade_count=None,
        taker_buy_base_volume=None, taker_buy_quote_volume=None,
        taker_sell_base_volume=None, taker_sell_quote_volume=None,
    )


def aggregate_htf(
    bars: list[CanonicalBar],
    minutes: int,
    start_ms: Optional[int] = None,
    end_ms: Optional[int] = None,
) -> list[HtfBar]:
    """Small-fixture aggregator. Production uses aggregate_htf_streaming."""
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
        bar_end = bucket + step
        if len(present) == minutes:
            out.append(_htf_complete(present, bucket, minutes, bar_end))
        else:
            out.append(_htf_incomplete(bucket, minutes, bar_end, len(present)))
        bucket += step
    return out


def _htf_arrow_schema():
    import pyarrow as pa
    fields = [
        pa.field("open_time_ms", pa.int64()),
        pa.field("bar_end_exclusive_ms", pa.int64()),
        pa.field("available_at_ms", pa.int64()),
        pa.field("is_complete", pa.bool_()),
        pa.field("expected_constituents", pa.int32()),
        pa.field("observed_constituents", pa.int32()),
        pa.field("trade_count", pa.int64()),
    ]
    for name in DECIMAL_FIELDS:
        fields.append(pa.field(name, pa.string()))
    return pa.schema(fields)


def htf_to_parquet_bytes(rows: list[HtfBar]) -> bytes:
    require_pyarrow()
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
    pq.write_table(pa.table(arrays), buf, **PARQUET_WRITE_KWARGS)
    return buf.getvalue().to_pybytes()


def htf_from_parquet(path: Path) -> list[HtfBar]:
    require_pyarrow()
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


class _HtfStream:
    """Carry only the active bucket across partitions."""

    def __init__(self, minutes: int, start_ms: int, end_ms: int, path: Path):
        require_pyarrow()
        import pyarrow.parquet as pq

        self.minutes = minutes
        self.step = minutes * BAR_MS
        self.start_ms = start_ms
        self.end_ms = end_ms
        self.next_emit = start_ms
        self.cur: Optional[int] = None
        self.members: dict[int, tuple] = {}
        self.conflicts: set[int] = set()
        self.complete = 0
        self.incomplete = 0
        self._rows: dict[str, list] = {n: [] for n in (
            "open_time_ms", "bar_end_exclusive_ms", "available_at_ms",
            "is_complete", "expected_constituents", "observed_constituents",
            "trade_count", *DECIMAL_FIELDS,
        )}
        self._n = 0
        path.parent.mkdir(parents=True, exist_ok=True)
        self._schema = _htf_arrow_schema()
        self._writer = pq.ParquetWriter(str(path), self._schema, **PARQUET_WRITE_KWARGS)

    def consume(self, open_time: int, payload: tuple) -> None:
        if open_time < self.start_ms or open_time >= self.end_ms:
            return
        bucket = (open_time // self.step) * self.step
        if self.cur is None or bucket != self.cur:
            self._flush_until(bucket)
            self.cur = bucket
            self.members = {}
            self.conflicts = set()
        off = (open_time - bucket) // BAR_MS
        if off < 0 or off >= self.minutes:
            return
        if off in self.conflicts:
            return
        prev = self.members.get(off)
        if prev is not None:
            if prev == payload:
                return
            del self.members[off]
            self.conflicts.add(off)
            return
        self.members[off] = payload

    def finish(self) -> None:
        self._flush_until(self.end_ms)
        self._flush_batch()
        self._writer.close()

    def _flush_until(self, upto: int) -> None:
        if self.cur is not None:
            self._emit(self.cur, self.members)
            self.next_emit = self.cur + self.step
            self.cur = None
            self.members = {}
            self.conflicts = set()
        while self.next_emit < upto and self.next_emit < self.end_ms:
            self._emit(self.next_emit, {})
            self.next_emit += self.step

    def _emit(self, bucket: int, members: dict[int, tuple]) -> None:
        bar_end = bucket + self.step
        complete = (
            len(members) == self.minutes
            and all(i in members for i in range(self.minutes))
        )
        r = self._rows
        r["open_time_ms"].append(bucket)
        r["bar_end_exclusive_ms"].append(bar_end)
        r["available_at_ms"].append(bar_end)
        r["expected_constituents"].append(self.minutes)
        if complete:
            ordered = [members[i] for i in range(self.minutes)]
            r["is_complete"].append(True)
            r["observed_constituents"].append(self.minutes)
            r["open"].append(_dec_str(ordered[0][0]))
            r["high"].append(_dec_str(max(m[1] for m in ordered)))
            r["low"].append(_dec_str(min(m[2] for m in ordered)))
            r["close"].append(_dec_str(ordered[-1][3]))
            r["base_volume"].append(_dec_str(sum((m[4] for m in ordered), Decimal(0))))
            r["quote_volume"].append(_dec_str(sum((m[5] for m in ordered), Decimal(0))))
            r["trade_count"].append(sum(m[6] for m in ordered))
            r["taker_buy_base_volume"].append(_dec_str(sum((m[7] for m in ordered), Decimal(0))))
            r["taker_buy_quote_volume"].append(_dec_str(sum((m[8] for m in ordered), Decimal(0))))
            r["taker_sell_base_volume"].append(_dec_str(sum((m[9] for m in ordered), Decimal(0))))
            r["taker_sell_quote_volume"].append(_dec_str(sum((m[10] for m in ordered), Decimal(0))))
            self.complete += 1
        else:
            r["is_complete"].append(False)
            r["observed_constituents"].append(len(members))
            r["trade_count"].append(None)
            for name in DECIMAL_FIELDS:
                r[name].append(None)
            self.incomplete += 1
        self._n += 1
        if self._n >= HTF_WRITE_BATCH_ROWS:
            self._flush_batch()

    def _flush_batch(self) -> None:
        if self._n == 0:
            return
        import pyarrow as pa
        table = pa.table(self._rows, schema=self._schema)
        self._writer.write_table(table)
        for k in self._rows:
            self._rows[k] = []
        self._n = 0


def aggregate_htf_streaming(root: Path, objects: list[SourceObject]) -> dict:
    """One chronological 1m scan, four HTF writers, O(bucket) carry state."""
    require_pyarrow()
    start_ms, end_ms = frozen_range_ms()
    streams = {
        name: _HtfStream(minutes, start_ms, end_ms, htf_path(root, name))
        for name, minutes in HTF_SPEC
    }
    cols = [
        "open_time_ms", "open", "high", "low", "close",
        "base_volume", "quote_volume", "trade_count",
        "taker_buy_base_volume", "taker_buy_quote_volume",
        "taker_sell_base_volume", "taker_sell_quote_volume",
    ]
    for batch in iter_canonical_batches(root, objects, columns=cols):
        n = batch.num_rows
        times = batch.column("open_time_ms").to_pylist()
        opens = batch.column("open").to_pylist()
        highs = batch.column("high").to_pylist()
        lows = batch.column("low").to_pylist()
        closes = batch.column("close").to_pylist()
        bvs = batch.column("base_volume").to_pylist()
        qvs = batch.column("quote_volume").to_pylist()
        tcs = batch.column("trade_count").to_pylist()
        tbs = batch.column("taker_buy_base_volume").to_pylist()
        tqs = batch.column("taker_buy_quote_volume").to_pylist()
        tsbs = batch.column("taker_sell_base_volume").to_pylist()
        tsqs = batch.column("taker_sell_quote_volume").to_pylist()
        for i in range(n):
            payload = (
                Decimal(opens[i]), Decimal(highs[i]), Decimal(lows[i]), Decimal(closes[i]),
                Decimal(bvs[i]), Decimal(qvs[i]), int(tcs[i]),
                Decimal(tbs[i]), Decimal(tqs[i]), Decimal(tsbs[i]), Decimal(tsqs[i]),
            )
            t = int(times[i])
            for stream in streams.values():
                stream.consume(t, payload)
    summary = {}
    for name, stream in streams.items():
        stream.finish()
        path = htf_path(root, name)
        summary[name] = {
            "expected_buckets": stream.complete + stream.incomplete,
            "complete_buckets": stream.complete,
            "incomplete_buckets": stream.incomplete,
            "path": str(path.relative_to(root)).replace("\\", "/"),
            "sha256": sha256_of_file(path),
        }
    return summary


def bars_available_at_1m(bars: list[CanonicalBar], decision_time_ms: int) -> list[CanonicalBar]:
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
    source_identities.sort(key=lambda r: (r["archive_class"] or "", r["source_period"] or ""))
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
                "Candidate artifact only. SNAPSHOT_CANDIDATE_READY is not "
                "ACCEPTED_FOR_DISCOVERY. Do not copy these values into "
                f"{REPO_MANIFEST_PATH} until a later human acceptance step."
            ),
        },
    }


def quality_report_markdown(quality: dict, snapshot_id: str | None = None) -> str:
    c = quality.get("continuity", {})
    snap = snapshot_id or quality.get("snapshot_id")
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
        DECIMAL_STRING_POLICY,
        "",
        "SNAPSHOT_CANDIDATE_READY is not ACCEPTED_FOR_DISCOVERY.",
        "The repository planning manifest remains unpromoted.",
        "",
    ]) + "\n"
