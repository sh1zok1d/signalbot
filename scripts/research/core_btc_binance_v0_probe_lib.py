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

Red-team remediation round (RT-01..RT-09) on top of the initial version:
strict calendar-complete `month_passed`/`local_audit_passed` (RT-01),
checksum filename identity (RT-02), exact zip-member identity (RT-03),
non-finite numerics never crash the audit (RT-04), and a corrected
malformed-header/BOM classifier (RT-07). RT-05/RT-06/RT-08/RT-10 live in the
CLI module.
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

# docs/CORE_BTC_BINANCE_V0_CONTRACT.md section 1: the raw archive carries
# exactly 12 columns; the research table retains the first 11 semantic
# fields. RT-09: 13+ columns must never be silently truncated/accepted.
EXPECTED_KLINE_COLUMNS = 12
BAR_SECONDS = 60
BAR_MS = BAR_SECONDS * 1000
NUMERIC_TOLERANCE = Decimal("0.00000001")

REPORT_SCHEMA_VERSION = 2
REPORT_KIND = "CORE_BTC_BINANCE_V0_SOURCE_PROBE"
# Bumped alongside the RT-01..RT-10 red-team remediation: report shape and
# status vocabulary changed materially (new fields, new checksum/local-audit
# statuses, a stricter month_passed predicate).
PROBE_TOOL_VERSION = 2
MONTH_PASS_PREDICATE_VERSION = "v2-calendar-complete-required"

SOURCE_PROBE_PASSED = "SOURCE_PROBE_PASSED"
SOURCE_PROBE_FAILED = "SOURCE_PROBE_FAILED"
SOURCE_PROBE_INCOMPLETE = "SOURCE_PROBE_INCOMPLETE"
LOCAL_AUDIT_PASSED = "LOCAL_AUDIT_PASSED"
LOCAL_AUDIT_FAILED = "LOCAL_AUDIT_FAILED"
LOCAL_AUDIT_INCOMPLETE = "LOCAL_AUDIT_INCOMPLETE"

DATASET_ACCEPTANCE_NOTE = (
    "SOURCE_PROBE_PASSED and LOCAL_AUDIT_PASSED are source-capability/local-"
    "evidence signals only. NOT one of them is equivalent to DATASET_ACCEPTED, "
    "MATERIALIZED_UNVERIFIED, QUALITY_AUDITED or "
    "ACCEPTED_FOR_DISCOVERY/ACCEPTED_FOR_CONFIRMATORY under "
    "docs/CORE_BTC_BINANCE_V0_CONTRACT.md section 11. The full historical "
    "dataset still requires complete acquisition, continuity audit, revision "
    "identity, deterministic materialization and the acceptance gates in "
    "that contract before any research claim may rely on it. Note also that "
    "this four-month probe's month_passed/local_audit_passed require an "
    "exactly calendar-complete month (see docs/CORE_BTC_BINANCE_V0_CONTRACT.md "
    "section 12: a non-zero gap count does not automatically kill the "
    "eventual full multi-year dataset -- that is a separate, later question "
    "this small probe does not answer)."
)

_YEAR_MONTH_RE = re.compile(r"^(\d{4})-(\d{2})$")

# RT-07: header detection must require known Binance-style header semantics,
# never "first cell fails int() => header" (that silently misclassified a
# genuinely malformed data row as a header and dropped it uncounted).
_KNOWN_HEADER_FIRST_TOKENS = {"open_time", "opentime", "open time"}
_UTF8_BOM = "﻿"


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


def expected_csv_member_name(year_month: str) -> str:
    """RT-03: the exact required in-archive member name. No sole-CSV
    fallback is ever accepted -- see `read_kline_csv_member`."""
    validate_year_month(year_month)
    return f"{SYMBOL}-{INTERVAL}-{year_month}.csv"


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
    'no checksum available', it's a distinct capability downgrade.

    Normalizes only the GNU `sha256sum --binary` `*filename` marker; the
    filename identity itself is NOT validated here (that needs the caller's
    expected object name -- see `evaluate_checksum_verification`)."""
    stripped = text.strip()
    if not stripped:
        raise CoreBtcBinanceV0ProbeError("empty checksum file")
    parts = stripped.split(None, 1)
    candidate = parts[0].strip()
    if len(candidate) != 64 or not re.fullmatch(r"[0-9a-fA-F]{64}", candidate):
        raise CoreBtcBinanceV0ProbeError(
            f"checksum file's first token is not a 64-hex-char sha256 digest: {candidate!r}")
    filename = parts[1].strip() if len(parts) > 1 else ""
    if filename.startswith("*"):
        filename = filename[1:]
    return {"sha256": candidate.lower(), "filename": filename}


def evaluate_checksum_verification(
    local_sha256: Optional[str], parsed_checksum: Optional[dict], expected_zip_filename: str,
) -> str:
    """RT-02: a checksum is only `VERIFIED` when BOTH the sha256 digest
    matches AND the checksum text's own filename identifies exactly the
    expected object (`BTCUSDT-1m-YYYY-MM.zip`) -- not another symbol,
    interval, month, or a daily-archive filename, and not a hash with no
    filename at all ("hash only" must never become `VERIFIED`)."""
    if parsed_checksum is None:
        return "NOT_VERIFIABLE_MISSING_CHECKSUM"
    if local_sha256 != parsed_checksum["sha256"]:
        return "MISMATCH"
    if parsed_checksum["filename"] != expected_zip_filename:
        return "FILENAME_IDENTITY_MISMATCH"
    return "VERIFIED"


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
      not overwrite this file (or its checksum sidecar -- see RT-05 in the
      CLI module) automatically; the old revision is preserved and a
      distinct revision identity/output directory is required to adopt the
      new bytes.
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


def _strip_bom(text: str) -> str:
    return text[1:] if text.startswith(_UTF8_BOM) else text


def _looks_like_header_token(token: str) -> bool:
    """RT-07: only a KNOWN Binance-style header token is treated as a
    header. A data-shaped row with an invalid/garbage first cell (e.g. a
    float timestamp, or corrupt text) is NOT a header -- it must fall
    through to row parsing and be counted malformed there, never silently
    dropped as if it were a header line."""
    normalized = token.strip().strip('"').lower()
    return normalized in _KNOWN_HEADER_FIRST_TOKENS


def parse_kline_csv(text: str) -> tuple[list[KlineRow], dict]:
    """Parse one archive member's CSV text into `KlineRow`s.

    Handles an optional header row (some archive eras include one, some do
    not) but never silently reinterprets a genuinely different schema: any
    row without EXACTLY the expected 12 columns (RT-09 -- neither fewer nor
    13+ silently truncated), or a column that fails to parse as the expected
    numeric type, or any numeric market field that parses but is non-finite
    (NaN/Infinity/-Infinity -- RT-04), is counted as malformed and excluded
    from the parsed rows rather than guessed at or allowed to crash a later
    comparison."""
    text = _strip_bom(text)
    rows_raw = list(csv.reader(io.StringIO(text)))
    header_present = False
    if rows_raw and rows_raw[0] and _looks_like_header_token(rows_raw[0][0]):
        header_present = True
        rows_raw = rows_raw[1:]

    parsed: list[KlineRow] = []
    malformed_row_indices: list[int] = []
    for idx, raw in enumerate(rows_raw):
        if not raw or len(raw) != EXPECTED_KLINE_COLUMNS:
            malformed_row_indices.append(idx)
            continue
        try:
            open_ = Decimal(raw[1])
            high = Decimal(raw[2])
            low = Decimal(raw[3])
            close = Decimal(raw[4])
            base_volume = Decimal(raw[5])
            quote_volume = Decimal(raw[7])
            taker_buy_base_volume = Decimal(raw[9])
            taker_buy_quote_volume = Decimal(raw[10])
            for value in (open_, high, low, close, base_volume, quote_volume,
                          taker_buy_base_volume, taker_buy_quote_volume):
                if not value.is_finite():
                    raise InvalidOperation("non-finite numeric field")
            row = KlineRow(
                open_time_ms=int(raw[0]),
                open=open_,
                high=high,
                low=low,
                close=close,
                base_volume=base_volume,
                close_time_ms=int(raw[6]),
                quote_volume=quote_volume,
                trade_count=int(raw[8]),
                taker_buy_base_volume=taker_buy_base_volume,
                taker_buy_quote_volume=taker_buy_quote_volume,
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
    """Read the kline CSV member out of a monthly archive zip.

    RT-03: the archive must contain the EXACT member
    `BTCUSDT-1m-YYYY-MM.csv`. There is no "sole CSV fallback" -- a
    differently-named CSV (wrong symbol/interval/daily-shaped filename, a
    path-prefixed or path-traversal name, etc) is never accepted as this
    month's evidence, even if it is the only CSV in the archive. No
    filesystem extraction happens; the member is read directly from the
    open `ZipFile` in memory.

    Returns `(csv_text_or_None, member_names, parser_status)`. Never raises
    for an unexpected archive shape -- that is a `parser_status` value the
    caller records, not a crash."""
    if not zip_path.exists():
        return None, [], "NO_SUCH_FILE"
    expected_member = expected_csv_member_name(year_month)
    try:
        with zipfile.ZipFile(zip_path) as zf:
            names = zf.namelist()
            if not names:
                return None, names, "EMPTY_ARCHIVE"
            if expected_member not in names:
                return None, names, "MISSING_EXPECTED_CSV_MEMBER"
            with zf.open(expected_member) as fh:
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
    """RT-04/RT-09: integer-only checks (minute alignment, close_time bound)
    are always safe and run first. Every numeric market field is then
    checked for finiteness BEFORE any ordered Decimal comparison -- a
    NaN/Infinity/-Infinity field makes every subsequent `<`/`>` comparison
    both meaningless and, for `decimal.Decimal`, liable to raise
    `InvalidOperation` -- so this function returns immediately after
    reporting which fields are non-finite rather than risk that crash."""
    violations: list[str] = []

    if row.open_time_ms % BAR_MS != 0:
        violations.append("open_time_not_minute_aligned")
    if row.close_time_ms < row.open_time_ms:
        violations.append("close_time_before_open_time")
    if row.close_time_ms >= row.open_time_ms + BAR_MS:
        violations.append("close_time_not_compatible_with_one_minute_bar")
    if row.trade_count < 0:
        violations.append("trade_count_negative")

    decimal_fields = (
        ("open", row.open), ("high", row.high), ("low", row.low), ("close", row.close),
        ("base_volume", row.base_volume), ("quote_volume", row.quote_volume),
        ("taker_buy_base_volume", row.taker_buy_base_volume),
        ("taker_buy_quote_volume", row.taker_buy_quote_volume),
    )
    non_finite_fields = [name for name, value in decimal_fields if not value.is_finite()]
    if non_finite_fields:
        violations.extend(f"{name}_not_finite" for name in non_finite_fields)
        return violations

    for name, value in (("open", row.open), ("high", row.high), ("low", row.low), ("close", row.close)):
        if value <= 0:
            violations.append(f"{name}_not_positive")
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
    if row.taker_buy_base_volume < 0:
        violations.append("taker_buy_base_volume_negative")
    if row.taker_buy_quote_volume < 0:
        violations.append("taker_buy_quote_volume_negative")
    if row.taker_buy_base_volume > row.base_volume + NUMERIC_TOLERANCE:
        violations.append("taker_buy_base_volume_exceeds_total")
    if row.taker_buy_quote_volume > row.quote_volume + NUMERIC_TOLERANCE:
        violations.append("taker_buy_quote_volume_exceeds_total")
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


def _passes_checksum_and_structural_completeness_gate(record: dict) -> bool:
    """Shared RT-01 completeness gate used by BOTH `evaluate_month_pass`
    (network-confirmed evidence) and `evaluate_local_audit_pass` (local-only
    evidence). For THIS four-month source-capability probe, a month may pass
    only when the canonical monthly grid is exactly complete: zero
    malformed/duplicate rows, zero invariant violations, strictly ordered,
    no rows outside the month's own bounds, and the observed unique
    open_times exactly equal the expected calendar-month row count with the
    first/last minute landing exactly on the month's own UTC boundaries.

    This is intentionally stricter than `docs/CORE_BTC_BINANCE_V0_CONTRACT.md`
    section 12's later full-dataset policy ("a non-zero gap count does not
    automatically kill the dataset") -- that later policy is about whether
    the EVENTUAL multi-year dataset may contain genuine historical gaps and
    still be usable. This probe asks a narrower, prior question: did the
    expected official monthly archive object -- for these four
    hand-picked, error-free months -- contain a canonical, complete monthly
    1m grid? An empty/partial CSV must never pass that question."""
    if (record.get("checksum_verification") != "VERIFIED"
            or record.get("parser_status") != "OK"
            or record.get("malformed_row_count") != 0
            or record.get("duplicate_count") != 0
            or record.get("invariant_violation_count") != 0
            or record.get("is_strictly_ordered_by_open_time") is not True
            or record.get("rows_outside_month_bounds") != []
            or record.get("missing_bucket_count") != 0):
        return False
    expected_rows = record.get("expected_rows")
    if not expected_rows or record.get("observed_unique_open_times") != expected_rows:
        return False
    year_month = record.get("year_month")
    if not year_month:
        return False
    start_ms, _ = month_bounds_ms(year_month)
    expected_last_open_ms = start_ms + (expected_rows - 1) * BAR_MS
    return (
        record.get("first_open_time_ms") == start_ms
        and record.get("last_open_time_ms") == expected_last_open_ms)


def evaluate_month_pass(record: dict) -> bool:
    """Whether one month's probe evidence supports the basic source-
    capability assumption AND was actually confirmed reachable over the
    network this run (`source_status` is `HTTP_200` or `REUSED_IDENTICAL`,
    i.e. checksum-verified against an object this run itself fetched or
    re-verified). This is the predicate that feeds `SOURCE_PROBE_PASSED` --
    see `evaluate_local_audit_pass` for the network-free counterpart."""
    if record.get("source_status") not in ("HTTP_200", "REUSED_IDENTICAL"):
        return False
    return _passes_checksum_and_structural_completeness_gate(record)


def evaluate_local_audit_pass(record: dict) -> bool:
    """RT-06: whether a LOCAL file -- never confirmed reachable from
    Binance in THIS run -- nonetheless passes the same checksum +
    structural-completeness bar as `evaluate_month_pass`, using only local
    evidence. This is a distinct, weaker claim than `SOURCE_PROBE_PASSED`:
    it proves the retained bytes are checksum-verified (against whatever
    `.CHECKSUM` sidecar is present on disk) and structurally complete -- not
    that Binance currently serves this object at the documented path.
    `audit-local` mode must never relabel this as network acquisition."""
    if record.get("source_status") != "LOCAL_FILE_PRESENT":
        return False
    return _passes_checksum_and_structural_completeness_gate(record)


def overall_probe_status(month_records: list[dict], mode: str) -> str:
    """RT-06: `audit-local` gets its own status vocabulary
    (`LOCAL_AUDIT_*`), kept conceptually separate from the network
    `SOURCE_PROBE_*` vocabulary used by `probe`/`inventory`."""
    if mode == "audit-local":
        if not month_records or any(rec.get("attempted") is not True for rec in month_records):
            return LOCAL_AUDIT_INCOMPLETE
        if all(rec.get("local_audit_passed") is True for rec in month_records):
            return LOCAL_AUDIT_PASSED
        return LOCAL_AUDIT_FAILED

    if not month_records:
        return SOURCE_PROBE_INCOMPLETE
    if any(rec.get("attempted") is not True for rec in month_records):
        return SOURCE_PROBE_INCOMPLETE
    if all(rec.get("month_passed") is True for rec in month_records):
        return SOURCE_PROBE_PASSED
    return SOURCE_PROBE_FAILED
