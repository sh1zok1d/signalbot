"""Deterministic, network-free helpers for the `CORE_BTC_BINANCE_V0` source
probe (`scripts/research/core_btc_binance_v0_probe.py`).

This module is intentionally pure: URL/filename construction, checksum-text
parsing, kline CSV parsing, the 1m structural audit and the existing-file
revision policy all live here so they can be unit tested with local
synthetic fixtures and never require network access.

Everything here follows the frozen `docs/CORE_BTC_BINANCE_V0_CONTRACT.md` and
`docs/manifests/CORE_BTC_BINANCE_V0.yaml`. It does not invent new dataset
semantics -- it only proves or falsifies the source-capability assumptions
those documents already state (official archive shape, checksum discipline,
12-column kline schema, UTC minute grid, no-lookahead availability).

Nothing in this module marks a dataset as accepted. See
`docs/CORE_BTC_BINANCE_V0_PROBE_RUNBOOK.md`.
"""
from __future__ import annotations

import csv
import hashlib
import io
import re
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Optional

UTC = timezone.utc

# ---------------------------------------------------------------------------
# frozen source identity (docs/CORE_BTC_BINANCE_V0_CONTRACT.md section 1-2)
# ---------------------------------------------------------------------------
PROVIDER = "binance"
MARKET_TYPE = "USD_M_FUTURES"
SYMBOL = "BTCUSDT"
INTERVAL = "1m"
ARCHIVE_CLASS = "monthly"
ARCHIVE_ROOT = "https://data.binance.vision/data/futures/um/monthly/klines"

# Source-capability probe months only -- NOT development/OOS research
# windows. Spans four different eras deliberately (pre-2021 bull run,
# 2021 mid-cycle, 2024, and the month immediately before this contract was
# frozen) so a systemic archive-shape change would be visible.
DEFAULT_PROBE_MONTHS = ("2020-01", "2021-05", "2024-03", "2026-07")

# docs/CORE_BTC_BINANCE_V0_CONTRACT.md section 1: the raw archive carries 12
# columns; the research table retains the first 11 semantic fields.
EXPECTED_KLINE_COLUMNS = 12
BAR_SECONDS = 60
BAR_MS = BAR_SECONDS * 1000
NUMERIC_TOLERANCE = Decimal("0.00000001")

REPORT_SCHEMA_VERSION = 1
REPORT_KIND = "CORE_BTC_BINANCE_V0_SOURCE_PROBE"

SOURCE_PROBE_PASSED = "SOURCE_PROBE_PASSED"
SOURCE_PROBE_FAILED = "SOURCE_PROBE_FAILED"
SOURCE_PROBE_INCOMPLETE = "SOURCE_PROBE_INCOMPLETE"

DATASET_ACCEPTANCE_NOTE = (
    "SOURCE_PROBE_PASSED is source-capability evidence only. It is NOT "
    "equivalent to DATASET_ACCEPTED, MATERIALIZED_UNVERIFIED, QUALITY_AUDITED "
    "or ACCEPTED_FOR_DISCOVERY/ACCEPTED_FOR_CONFIRMATORY under "
    "docs/CORE_BTC_BINANCE_V0_CONTRACT.md section 11. The full historical "
    "dataset still requires complete acquisition, continuity audit, revision "
    "identity, deterministic materialization and the acceptance gates in "
    "that contract before any research claim may rely on it."
)

_YEAR_MONTH_RE = re.compile(r"^(\d{4})-(\d{2})$")


class CoreBtcBinanceV0ProbeError(ValueError):
    """Raised for malformed probe inputs (bad year-month, malformed checksum
    text, etc). Never raised for ordinary source absence -- that is recorded
    as a status field, not an exception."""


# ---------------------------------------------------------------------------
# identity / URL construction (responsibility 1: source inventory)
# ---------------------------------------------------------------------------
def validate_year_month(year_month: str) -> None:
    m = _YEAR_MONTH_RE.match(year_month)
    if not m or not (1 <= int(m.group(2)) <= 12):
        raise CoreBtcBinanceV0ProbeError(
            f"probe month must be 'YYYY-MM' with a valid month, got {year_month!r}")


def archive_object_name(year_month: str) -> str:
    validate_year_month(year_month)
    return f"{SYMBOL}-{INTERVAL}-{year_month}.zip"


def archive_urls(year_month: str) -> tuple[str, str]:
    """Returns (zip_url, checksum_url). Does not claim the object exists --
    HTTP/source absence is recorded explicitly by the caller, never assumed
    away here."""
    zip_name = archive_object_name(year_month)
    base = f"{ARCHIVE_ROOT}/{SYMBOL}/{INTERVAL}"
    return f"{base}/{zip_name}", f"{base}/{zip_name}.CHECKSUM"


def local_zip_filename(year_month: str) -> str:
    return archive_object_name(year_month)


def local_checksum_filename(year_month: str) -> str:
    return f"{archive_object_name(year_month)}.CHECKSUM"


# ---------------------------------------------------------------------------
# checksum parsing/verification (responsibility 2: acquisition + checksum)
# ---------------------------------------------------------------------------
def parse_checksum_text(text: str) -> dict:
    """Parse a Binance `.CHECKSUM` object (`sha256sum`-style: hex digest,
    whitespace, filename). Raises `CoreBtcBinanceV0ProbeError` for empty or
    malformed content -- a malformed checksum must never be treated as
    'no checksum available', it's a distinct capability downgrade."""
    stripped = text.strip()
    if not stripped:
        raise CoreBtcBinanceV0ProbeError("empty checksum file")
    parts = stripped.split(None, 1)
    candidate = parts[0].strip()
    if len(candidate) != 64 or not re.fullmatch(r"[0-9a-fA-F]{64}", candidate):
        raise CoreBtcBinanceV0ProbeError(
            f"checksum file's first token is not a 64-hex-char sha256 digest: {candidate!r}")
    filename = parts[1].strip() if len(parts) > 1 else ""
    return {"sha256": candidate.lower(), "filename": filename}


def sha256_of_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_of_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# existing-file disposition outcomes -- see docstring on
# `decide_existing_zip_disposition` for the policy these implement.
DISPOSITION_NEW = "NEW"
DISPOSITION_REUSED_IDENTICAL = "REUSED_IDENTICAL"
DISPOSITION_REUSED_UNVERIFIED_NO_REFERENCE = "REUSED_UNVERIFIED_NO_REFERENCE"
DISPOSITION_REVISION_CONFLICT = "REVISION_CONFLICT"


def decide_existing_zip_disposition(
    existing_sha256: Optional[str], expected_sha256: Optional[str],
) -> str:
    """Raw-file rule: never silently overwrite an existing source object if
    its bytes differ.

    - no existing file -> `NEW` (caller downloads).
    - existing file, and the source's own published checksum is known and
      matches it -> `REUSED_IDENTICAL` (safe to reuse, verified).
    - existing file, and the source's own published checksum is known but
      does NOT match it -> `REVISION_CONFLICT`. Fail closed: the caller must
      not overwrite this file automatically; the old revision is preserved
      and a distinct revision identity/output directory is required to
      adopt the new bytes.
    - existing file, but no authoritative published checksum is available
      to compare against (missing/malformed `.CHECKSUM`) -> we have no
      reference to decide "identical vs different" from, so the safest
      default is to leave the existing bytes untouched rather than gamble on
      overwriting: `REUSED_UNVERIFIED_NO_REFERENCE`."""
    if existing_sha256 is None:
        return DISPOSITION_NEW
    if expected_sha256 is None:
        return DISPOSITION_REUSED_UNVERIFIED_NO_REFERENCE
    if existing_sha256 == expected_sha256:
        return DISPOSITION_REUSED_IDENTICAL
    return DISPOSITION_REVISION_CONFLICT


# ---------------------------------------------------------------------------
# kline parsing (responsibility 3: local 1m structural audit)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class KlineRow:
    """One parsed USD-M futures 1m kline row.

    `open_time_ms`/`close_time_ms` are kept distinct on purpose: per
    `docs/CORE_BTC_BINANCE_V0_CONTRACT.md` section 5, availability is
    modeled as `open_time_ms + 60_000` (`bar_end_exclusive`), never
    `close_time_ms`. This dataclass preserves both raw fields so that rule
    can be enforced later; it does not itself compute availability."""
    open_time_ms: int
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    base_volume: Decimal
    close_time_ms: int
    quote_volume: Decimal
    trade_count: int
    taker_buy_base_volume: Decimal
    taker_buy_quote_volume: Decimal


def bar_end_exclusive_ms(open_time_ms: int) -> int:
    """`docs/CORE_BTC_BINANCE_V0_CONTRACT.md` section 5: a closed 1m row is
    not available before `open_time + 60s`. Never derive this from
    `close_time_ms`."""
    return open_time_ms + BAR_MS


def _looks_like_header_token(token: str) -> bool:
    try:
        int(token)
    except ValueError:
        return True
    return False


def parse_kline_csv(text: str) -> tuple[list[KlineRow], dict]:
    """Parse one archive member's CSV text into `KlineRow`s.

    Handles an optional header row (some archive eras include one, some do
    not) but never silently reinterprets a genuinely different schema: any
    row with fewer than the expected 12 columns, or a column that fails to
    parse as the expected numeric type, is counted as malformed and
    excluded from the parsed rows rather than guessed at."""
    rows_raw = list(csv.reader(io.StringIO(text)))
    header_present = False
    if rows_raw and rows_raw[0] and _looks_like_header_token(rows_raw[0][0]):
        header_present = True
        rows_raw = rows_raw[1:]

    parsed: list[KlineRow] = []
    malformed_row_indices: list[int] = []
    for idx, raw in enumerate(rows_raw):
        if not raw or len(raw) < EXPECTED_KLINE_COLUMNS:
            malformed_row_indices.append(idx)
            continue
        try:
            row = KlineRow(
                open_time_ms=int(raw[0]),
                open=Decimal(raw[1]),
                high=Decimal(raw[2]),
                low=Decimal(raw[3]),
                close=Decimal(raw[4]),
                base_volume=Decimal(raw[5]),
                close_time_ms=int(raw[6]),
                quote_volume=Decimal(raw[7]),
                trade_count=int(raw[8]),
                taker_buy_base_volume=Decimal(raw[9]),
                taker_buy_quote_volume=Decimal(raw[10]),
            )
        except (InvalidOperation, ValueError):
            malformed_row_indices.append(idx)
            continue
        parsed.append(row)

    meta = {
        "header_present": header_present,
        "total_raw_rows": len(rows_raw),
        "malformed_row_indices": malformed_row_indices,
        "malformed_row_count": len(malformed_row_indices),
    }
    return parsed, meta


def read_kline_csv_member(zip_path: Path, year_month: str) -> tuple[Optional[str], list[str], str]:
    """Read the single kline CSV member out of a monthly archive zip.

    Returns `(csv_text_or_None, member_names, parser_status)`. Never raises
    for an unexpected archive shape -- that is a `parser_status` value the
    caller records, not a crash."""
    if not zip_path.exists():
        return None, [], "NO_SUCH_FILE"
    try:
        with zipfile.ZipFile(zip_path) as zf:
            names = zf.namelist()
            if not names:
                return None, names, "EMPTY_ARCHIVE"
            expected_member = f"{SYMBOL}-{INTERVAL}-{year_month}.csv"
            if expected_member in names:
                member = expected_member
            else:
                csv_members = [n for n in names if n.lower().endswith(".csv")]
                if len(csv_members) != 1:
                    return None, names, "UNEXPECTED_ZIP_MEMBERS"
                member = csv_members[0]
            with zf.open(member) as fh:
                text = fh.read().decode("utf-8")
            return text, names, "OK"
    except zipfile.BadZipFile:
        return None, [], "BAD_ZIP_FILE"


# ---------------------------------------------------------------------------
# structural audit
# ---------------------------------------------------------------------------
def month_bounds_ms(year_month: str) -> tuple[int, int]:
    validate_year_month(year_month)
    year, month = (int(part) for part in year_month.split("-"))
    start = datetime(year, month, 1, tzinfo=UTC)
    end = datetime(year + 1, 1, 1, tzinfo=UTC) if month == 12 else datetime(year, month + 1, 1, tzinfo=UTC)
    return int(start.timestamp() * 1000), int(end.timestamp() * 1000)


def expected_bucket_starts(year_month: str) -> list[int]:
    start_ms, end_ms = month_bounds_ms(year_month)
    return list(range(start_ms, end_ms, BAR_MS))


def row_invariant_violations(row: KlineRow) -> list[str]:
    violations = []
    for name, value in (("open", row.open), ("high", row.high), ("low", row.low), ("close", row.close)):
        if not value.is_finite() or value <= 0:
            violations.append(f"{name}_not_finite_positive")
    if row.high < max(row.open, row.close):
        violations.append("high_lt_max_open_close")
    if row.low > min(row.open, row.close):
        violations.append("low_gt_min_open_close")
    if row.high < row.low:
        violations.append("high_lt_low")
    if row.base_volume < 0:
        violations.append("base_volume_negative")
    if row.quote_volume < 0:
        violations.append("quote_volume_negative")
    if row.trade_count < 0:
        violations.append("trade_count_negative")
    if row.taker_buy_base_volume < 0:
        violations.append("taker_buy_base_volume_negative")
    if row.taker_buy_quote_volume < 0:
        violations.append("taker_buy_quote_volume_negative")
    if row.taker_buy_base_volume > row.base_volume + NUMERIC_TOLERANCE:
        violations.append("taker_buy_base_volume_exceeds_total")
    if row.taker_buy_quote_volume > row.quote_volume + NUMERIC_TOLERANCE:
        violations.append("taker_buy_quote_volume_exceeds_total")
    if row.close_time_ms < row.open_time_ms:
        violations.append("close_time_before_open_time")
    if row.close_time_ms >= row.open_time_ms + BAR_MS:
        violations.append("close_time_not_compatible_with_one_minute_bar")
    return violations


def compress_to_ranges(sorted_values: list[int], step: int) -> list[list[int]]:
    """Compress a sorted list of equally-spaced-when-contiguous integers
    into `[start, end]` inclusive ranges, so exact missing-timestamp ranges
    can be preserved without dumping one entry per missing minute."""
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


def audit_klines(rows: list[KlineRow], year_month: str, malformed_row_count: int) -> dict:
    """The 1m structural audit. Never fills missing bars, never synthesizes
    zero-volume bars, never repairs duplicates -- it only reports."""
    expected_starts = expected_bucket_starts(year_month)
    expected_set = set(expected_starts)
    observed_times = [row.open_time_ms for row in rows]

    is_strictly_ordered = all(
        observed_times[i] < observed_times[i + 1] for i in range(len(observed_times) - 1))

    counts: dict[int, int] = {}
    for t in observed_times:
        counts[t] = counts.get(t, 0) + 1
    duplicate_open_times = sorted(t for t, c in counts.items() if c > 1)
    duplicate_count = sum(c - 1 for c in counts.values() if c > 1)

    unique_times = set(observed_times)
    missing = sorted(expected_set - unique_times)
    rows_outside_month_bounds = sorted(t for t in unique_times if t not in expected_set)

    violations_by_row = []
    for row in rows:
        v = row_invariant_violations(row)
        if v:
            violations_by_row.append({"open_time_ms": row.open_time_ms, "violations": v})

    return {
        "expected_rows": len(expected_starts),
        "observed_rows": len(rows),
        "observed_unique_open_times": len(unique_times),
        "missing_bucket_count": len(missing),
        "duplicate_count": duplicate_count,
        "duplicate_open_times": duplicate_open_times,
        "missing_open_time_ranges_ms": compress_to_ranges(missing, BAR_MS),
        "rows_outside_month_bounds": rows_outside_month_bounds,
        "is_strictly_ordered_by_open_time": is_strictly_ordered,
        "malformed_row_count": malformed_row_count,
        "invariant_violation_count": len(violations_by_row),
        "invariant_violations": violations_by_row,
        "first_open_time_ms": observed_times[0] if observed_times else None,
        "last_open_time_ms": observed_times[-1] if observed_times else None,
    }


def evaluate_month_pass(record: dict) -> bool:
    """Whether one month's probe evidence supports the basic source-capability
    assumption -- NOT dataset acceptance. Requires the source object to exist
    and be checksum-verified, the archive to parse deterministically with
    zero malformed/duplicate rows and zero row-level invariant violations,
    and rows to be strictly ordered by `open_time`.

    A non-zero `missing_bucket_count` does NOT fail this check on its own:
    `docs/CORE_BTC_BINANCE_V0_CONTRACT.md` section 12 states a non-zero gap
    count does not automatically kill the dataset. Continuity is still
    recorded and must be inspected -- it is a different question from
    whether the source/schema/checksum assumptions hold at all."""
    return (
        record.get("source_status") in ("HTTP_200", "REUSED_IDENTICAL")
        and record.get("checksum_verification") == "VERIFIED"
        and record.get("parser_status") == "OK"
        and record.get("malformed_row_count") == 0
        and record.get("duplicate_count") == 0
        and record.get("invariant_violation_count") == 0
        and record.get("is_strictly_ordered_by_open_time") is True
    )


def overall_probe_status(month_records: list[dict]) -> str:
    if not month_records:
        return SOURCE_PROBE_INCOMPLETE
    if any(rec.get("attempted") is not True for rec in month_records):
        return SOURCE_PROBE_INCOMPLETE
    if all(rec.get("month_passed") is True for rec in month_records):
        return SOURCE_PROBE_PASSED
    return SOURCE_PROBE_FAILED
