"""MARKET_03_BINANCE_SPOT_BTCUSDT_1H_V0 dataset helpers.

Network-free: URL construction, checksum parsing, native 1h kline parsing,
integrity audit, Freqtrade timestamp mapping, funding record comparison,
and snapshot identity. Callers inject bytes.

This module does not compute EMA, funding percentile, trades, or any
MARKET-03 scientific quantity. It does not authorize B2-06 execution.
Protected 2025/2026 rows are rejected as out of acquisition bounds.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import zipfile
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional, Sequence

UTC = timezone.utc

DATASET_ID = "MARKET_03_BINANCE_SPOT_BTCUSDT_1H_V0"
PROVIDER = "Binance"
VENUE = "Binance"
MARKET_TYPE = "SPOT"
SYMBOL = "BTCUSDT"
INTERVAL = "1h"
BAR_SECONDS = 3600
BAR_MS = BAR_SECONDS * 1000
EXPECTED_KLINE_COLUMNS = 12
ARCHIVE_CLASS = "monthly"
ARCHIVE_ROOT = "https://data.binance.vision/data/spot/monthly/klines"
DOCUMENTED_API_ORIGIN = "/api/v3/klines"
PUBLIC_DATA_README = (
    "https://github.com/binance/binance-public-data/blob/master/README.md"
)

# Headline external timerange starts 2019-10-01. Freqtrade
# startup_candle_count=1300 on 1h requires history from 2019-08-07 20:00 UTC.
# Acquisition uses the complete native month that contains that warmup start.
ACQUIRE_START_MONTH = "2019-08"
ACQUIRE_END_MONTH_INCLUSIVE = "2024-12"
START_INCLUSIVE = "2019-08-01T00:00:00Z"
END_EXCLUSIVE = "2025-01-01T00:00:00Z"
PROTECTED_OOS_START_MS = int(
    datetime(2025, 1, 1, tzinfo=UTC).timestamp() * 1000
)
HEADLINE_TIMERANGE_START_MS = int(
    datetime(2019, 10, 1, tzinfo=UTC).timestamp() * 1000
)
STARTUP_CANDLE_COUNT = 1300
EMA_PERIOD_SHIPPED = 600

FUNDING_VISION_ROOT = (
    "https://data.binance.vision/data/futures/um/monthly/fundingRate/BTCUSDT"
)
FUNDING_REST_ENDPOINT = "https://fapi.binance.com/fapi/v1/fundingRate"
FUNDING_REST_FALLBACK_ENDPOINT = "https://www.binance.com/fapi/v1/fundingRate"
FUNDING_REST_PATH = "/fapi/v1/fundingRate"
FUNDING_PRODUCT = "USD_M_PERPETUAL"
FUNDING_SYMBOL = "BTCUSDT"
B2_06_DATASET_ID = "B2_06_BINANCE_UM_BTCUSDT_OI_FUNDING_V0"
B2_06_SNAPSHOT_ID = (
    "5a9d036b23721d75b519b8478b81e333791227376d25cbeea5f0666c90730a33"
)
B2_06_OBJECT_LEDGER = (
    "docs/research_data/B2_06_BINANCE_UM_BTCUSDT_OI_FUNDING_V0/"
    "OBJECT_LEDGER_5a9d036b.json"
)
FUNDING_VISION_START_MONTH = "2020-01"
FUNDING_REST_START_INCLUSIVE = "2019-09-01T00:00:00Z"
FUNDING_COMPARE_END_EXCLUSIVE = END_EXCLUSIVE

STRICT_HISTORICAL_PUBLICATION_LATENCY = "UNPROVEN"
REPRODUCTION_FUNDINGTIME_ASSUMPTION_MEANING = (
    "A funding observation is treated as available at its Binance fundingTime, "
    "matching the pinned external EmaCrossFunding implementation. This does not "
    "prove Binance publication latency is zero, does not prove live as-of "
    "availability, and does not solve the B2-06 publication-timing blocker."
)

KLINE_FIELDS = (
    "open_time",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "close_time",
    "quote_volume",
    "trade_count",
    "taker_buy_base_volume",
    "taker_buy_quote_volume",
    "ignore",
)

DUPLICATE_POLICY = "REJECT_DUPLICATE_OPEN_TIME_DO_NOT_KEEP_FIRST_OR_LAST"
GAP_POLICY = "ENUMERATE_MISSING_NATIVE_HOURS_DO_NOT_SYNTHESIZE"
NORMALIZATION_RULES = (
    "native_12_column_binance_spot_kline_csv",
    "preserve_decimal_strings",
    "open_time_ms_int",
    "no_forward_fill",
    "no_resample",
    "no_perp_substitute",
    "drop_ignore_column_from_canonical",
)

FORBIDDEN_MARKET_SUBSTITUTES = frozenset(
    {
        "USD_M_PERPETUAL",
        "COIN_M_PERPETUAL",
        "AGGREGATED_EXTERNAL_PRICE_FEED",
        "OTHER_EXCHANGE",
        "CORE_BTC_BINANCE_V0",
    }
)

_YEAR_MONTH_RE = re.compile(r"^(\d{4})-(\d{2})$")
_KNOWN_HEADER_FIRST_TOKENS = {"open_time", "opentime", "open time"}
_UTF8_BOM = "\ufeff"
_HEX64 = re.compile(r"^[0-9a-fA-F]{64}$")


class Market03SpotDatasetError(ValueError):
    """Malformed dataset-construction input. Ordinary source absence is a status."""


def dumps_deterministic(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def sha256_of_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_of_text(text: str) -> str:
    return sha256_of_bytes(text.encode("utf-8"))


def sha256_of_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_of_canonical_identity_payload(payload: Mapping[str, Any]) -> str:
    return sha256_of_text(dumps_deterministic(payload))


def validate_year_month(year_month: str) -> None:
    match = _YEAR_MONTH_RE.match(year_month)
    if not match or not (1 <= int(match.group(2)) <= 12):
        raise Market03SpotDatasetError(
            f"year-month must be 'YYYY-MM', got {year_month!r}"
        )


def month_start_utc(year_month: str) -> datetime:
    validate_year_month(year_month)
    year, month = (int(part) for part in year_month.split("-"))
    return datetime(year, month, 1, tzinfo=UTC)


def next_month_start_utc(year_month: str) -> datetime:
    start = month_start_utc(year_month)
    if start.month == 12:
        return datetime(start.year + 1, 1, 1, tzinfo=UTC)
    return datetime(start.year, start.month + 1, 1, tzinfo=UTC)


def month_bounds_ms(year_month: str) -> tuple[int, int]:
    start = month_start_utc(year_month)
    end = next_month_start_utc(year_month)
    return int(start.timestamp() * 1000), int(end.timestamp() * 1000)


def iter_year_months(start_month: str, end_month_inclusive: str) -> list[str]:
    validate_year_month(start_month)
    validate_year_month(end_month_inclusive)
    cursor = month_start_utc(start_month)
    end = month_start_utc(end_month_inclusive)
    if cursor > end:
        raise Market03SpotDatasetError("start month is after end month")
    months: list[str] = []
    while cursor <= end:
        months.append(f"{cursor.year:04d}-{cursor.month:02d}")
        cursor = (
            datetime(cursor.year + 1, 1, 1, tzinfo=UTC)
            if cursor.month == 12
            else datetime(cursor.year, cursor.month + 1, 1, tzinfo=UTC)
        )
    return months


def acquisition_months() -> list[str]:
    return iter_year_months(ACQUIRE_START_MONTH, ACQUIRE_END_MONTH_INCLUSIVE)


def refuse_protected_oos_month(year_month: str) -> None:
    validate_year_month(year_month)
    start_ms, _end_ms = month_bounds_ms(year_month)
    if start_ms >= PROTECTED_OOS_START_MS:
        raise Market03SpotDatasetError(
            f"refusing protected OOS month {year_month}: "
            "2025/2026 data are not acquired or inspected for MARKET-03"
        )


def expected_hourly_open_times_ms(year_month: str) -> list[int]:
    refuse_protected_oos_month(year_month)
    start_ms, end_ms = month_bounds_ms(year_month)
    end_ms = min(end_ms, PROTECTED_OOS_START_MS)
    return list(range(start_ms, end_ms, BAR_MS))


def expected_dataset_hour_count() -> int:
    total = 0
    for month in acquisition_months():
        total += len(expected_hourly_open_times_ms(month))
    return total


def warmup_open_time_ms() -> int:
    return HEADLINE_TIMERANGE_START_MS - (STARTUP_CANDLE_COUNT * BAR_MS)


def archive_object_name(year_month: str) -> str:
    validate_year_month(year_month)
    return f"{SYMBOL}-{INTERVAL}-{year_month}.zip"


def expected_csv_member_name(year_month: str) -> str:
    validate_year_month(year_month)
    return f"{SYMBOL}-{INTERVAL}-{year_month}.csv"


def archive_urls(year_month: str) -> tuple[str, str]:
    refuse_protected_oos_month(year_month)
    zip_name = archive_object_name(year_month)
    base = f"{ARCHIVE_ROOT}/{SYMBOL}/{INTERVAL}"
    return f"{base}/{zip_name}", f"{base}/{zip_name}.CHECKSUM"


def funding_archive_object_name(year_month: str) -> str:
    validate_year_month(year_month)
    return f"{SYMBOL}-fundingRate-{year_month}.zip"


def funding_csv_member_name(year_month: str) -> str:
    validate_year_month(year_month)
    return f"{SYMBOL}-fundingRate-{year_month}.csv"


def funding_archive_urls(year_month: str) -> tuple[str, str]:
    refuse_protected_oos_month(year_month)
    zip_name = funding_archive_object_name(year_month)
    return f"{FUNDING_VISION_ROOT}/{zip_name}", f"{FUNDING_VISION_ROOT}/{zip_name}.CHECKSUM"


def parse_checksum_text(text: str) -> dict[str, str]:
    stripped = text.strip()
    if not stripped:
        raise Market03SpotDatasetError("empty checksum file")
    parts = stripped.split(None, 1)
    candidate = parts[0].strip()
    if not _HEX64.fullmatch(candidate):
        raise Market03SpotDatasetError(
            f"checksum first token is not a 64-hex sha256: {candidate!r}"
        )
    filename = parts[1].strip() if len(parts) > 1 else ""
    if filename.startswith("*"):
        filename = filename[1:]
    return {"sha256": candidate.lower(), "filename": filename}


def evaluate_checksum_verification(
    local_sha256: Optional[str],
    parsed_checksum: Optional[Mapping[str, str]],
    expected_zip_filename: str,
) -> str:
    if parsed_checksum is None:
        return "NOT_VERIFIABLE_MISSING_CHECKSUM"
    if local_sha256 != parsed_checksum["sha256"]:
        return "MISMATCH"
    if parsed_checksum.get("filename") != expected_zip_filename:
        return "FILENAME_IDENTITY_MISMATCH"
    return "VERIFIED"


def iso_utc_from_ms(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000, tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def freqtrade_date_from_open_time_ms(open_time_ms: int) -> str:
    """Freqtrade dataframe `date` for a Binance kline is the candle open.

    ccxt/Freqtrade label 1h candles by open time, not close_time. Signalbot
    maps native Vision/API `open_time` → that same UTC instant.
    """
    return iso_utc_from_ms(open_time_ms)


def bar_end_exclusive_ms(open_time_ms: int) -> int:
    """Closed 1h spot bar is not available before open_time + 3600s.

    Do not substitute close_time_ms for availability.
    """
    return open_time_ms + BAR_MS


def kline_mapping_record() -> dict[str, Any]:
    return {
        "binance_raw_fields": list(KLINE_FIELDS),
        "binance_open_time_semantic": "candle_open_utc_ms",
        "binance_close_time_semantic": "last_millisecond_inside_source_bar",
        "binance_volume_semantic": "base_asset_volume",
        "documented_api_origin": DOCUMENTED_API_ORIGIN,
        "freqtrade_dataframe_date": "candle_open_utc_equal_to_open_time",
        "freqtrade_ohlcv_columns": ["date", "open", "high", "low", "close", "volume"],
        "freqtrade_signal_on": "closed_candle",
        "freqtrade_fill_docs": "next_candle_open",
        "signalbot_map": "freqtrade_date = datetime_utc(open_time_ms)",
        "availability_for_closed_bar": "bar_end_exclusive = open_time_ms + 3600000",
        "core_derived_1h_forbidden": (
            "CORE_BTC_BINANCE_V0 1h bars are USD-M perpetual aggregations "
            "and must not be substituted"
        ),
        "differences": [
            {
                "topic": "label_clock",
                "binance_raw": "open_time (ms) and close_time (ms)",
                "freqtrade": "single `date` column = open time",
            },
            {
                "topic": "volume_name",
                "binance_raw": "column 6 = base volume; column 8 = quote volume",
                "freqtrade": "`volume` is base volume",
            },
            {
                "topic": "closed_bar_availability",
                "binance_raw": "close_time is last ms inside the bar, typically open+3599999",
                "freqtrade": "populate_* runs on the closed candle; fill next open",
            },
            {
                "topic": "microsecond_era",
                "note": (
                    "Binance public data README: spot kline timestamps become "
                    "microseconds from 2025-01-01. This dataset excludes 2025+ "
                    "so remaining timestamps are milliseconds."
                ),
            },
        ],
    }


@dataclass(frozen=True)
class SpotKlineRow:
    open_time_ms: int
    open: str
    high: str
    low: str
    close: str
    volume: str
    close_time_ms: int
    quote_volume: str
    trade_count: int
    taker_buy_base_volume: str
    taker_buy_quote_volume: str

    def canonical_dict(self) -> dict[str, Any]:
        return {
            "close": self.close,
            "close_time_ms": self.close_time_ms,
            "high": self.high,
            "low": self.low,
            "open": self.open,
            "open_time_ms": self.open_time_ms,
            "quote_volume": self.quote_volume,
            "taker_buy_base_volume": self.taker_buy_base_volume,
            "taker_buy_quote_volume": self.taker_buy_quote_volume,
            "trade_count": self.trade_count,
            "volume": self.volume,
        }


def _strip_bom(text: str) -> str:
    return text[1:] if text.startswith(_UTF8_BOM) else text


def _looks_like_header_token(token: str) -> bool:
    normalized = token.strip().strip('"').lower()
    return normalized in _KNOWN_HEADER_FIRST_TOKENS


def _finite_decimal(value: str, field: str) -> Decimal:
    parsed = Decimal(value)
    if not parsed.is_finite():
        raise InvalidOperation(f"non-finite {field}")
    return parsed


def parse_spot_kline_csv(text: str) -> tuple[list[SpotKlineRow], dict[str, Any]]:
    text = _strip_bom(text)
    rows_raw = list(csv.reader(io.StringIO(text)))
    header_present = False
    if rows_raw and rows_raw[0] and _looks_like_header_token(rows_raw[0][0]):
        header_present = True
        rows_raw = rows_raw[1:]

    parsed: list[SpotKlineRow] = []
    malformed_row_indices: list[int] = []
    for idx, raw in enumerate(rows_raw):
        if not raw or len(raw) != EXPECTED_KLINE_COLUMNS:
            malformed_row_indices.append(idx)
            continue
        try:
            open_time_ms = int(raw[0])
            close_time_ms = int(raw[6])
            if open_time_ms >= PROTECTED_OOS_START_MS:
                raise Market03SpotDatasetError(
                    "protected OOS kline present in acquired member; "
                    "acquisition bounds were violated"
                )
            _finite_decimal(raw[1], "open")
            _finite_decimal(raw[2], "high")
            _finite_decimal(raw[3], "low")
            _finite_decimal(raw[4], "close")
            _finite_decimal(raw[5], "volume")
            _finite_decimal(raw[7], "quote_volume")
            _finite_decimal(raw[9], "taker_buy_base_volume")
            _finite_decimal(raw[10], "taker_buy_quote_volume")
            row = SpotKlineRow(
                open_time_ms=open_time_ms,
                open=raw[1],
                high=raw[2],
                low=raw[3],
                close=raw[4],
                volume=raw[5],
                close_time_ms=close_time_ms,
                quote_volume=raw[7],
                trade_count=int(raw[8]),
                taker_buy_base_volume=raw[9],
                taker_buy_quote_volume=raw[10],
            )
        except Market03SpotDatasetError:
            raise
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


def read_zip_csv_member(
    zip_bytes: bytes, expected_member: str,
) -> tuple[Optional[str], list[str], str]:
    try:
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as archive:
            names = archive.namelist()
            if not names:
                return None, names, "EMPTY_ARCHIVE"
            if expected_member not in names:
                return None, names, "MISSING_EXPECTED_CSV_MEMBER"
            with archive.open(expected_member) as handle:
                text = handle.read().decode("utf-8")
            return text, names, "OK"
    except zipfile.BadZipFile:
        return None, [], "BAD_ZIP_FILE"
    except UnicodeDecodeError:
        return None, [], "NON_UTF8_MEMBER"


def row_invariant_violations(row: SpotKlineRow) -> list[str]:
    violations: list[str] = []
    if row.open_time_ms % BAR_MS != 0:
        violations.append("open_time_not_hour_aligned")
    if row.open_time_ms >= PROTECTED_OOS_START_MS:
        violations.append("protected_oos_timestamp")
    if row.close_time_ms < row.open_time_ms:
        violations.append("close_time_before_open_time")
    if row.close_time_ms >= bar_end_exclusive_ms(row.open_time_ms):
        violations.append("close_time_not_inside_bar")
    try:
        open_ = Decimal(row.open)
        high = Decimal(row.high)
        low = Decimal(row.low)
        close = Decimal(row.close)
        volume = Decimal(row.volume)
    except InvalidOperation:
        return [*violations, "non_decimal_ohlcv"]
    for name, value in (
        ("open", open_),
        ("high", high),
        ("low", low),
        ("close", close),
    ):
        if value <= 0:
            violations.append(f"non_positive_{name}")
        if not value.is_finite():
            violations.append(f"non_finite_{name}")
    if volume < 0:
        violations.append("negative_volume")
    if high < max(open_, close, low):
        violations.append("high_below_ohlc")
    if low > min(open_, close, high):
        violations.append("low_above_ohlc")
    return violations


def compress_to_ranges(values: Sequence[int], step: int) -> list[dict[str, int]]:
    if not values:
        return []
    ranges: list[dict[str, int]] = []
    start = prev = values[0]
    for value in values[1:]:
        if value == prev + step:
            prev = value
            continue
        ranges.append({"start_ms": start, "end_ms": prev, "count": ((prev - start) // step) + 1})
        start = prev = value
    ranges.append({"start_ms": start, "end_ms": prev, "count": ((prev - start) // step) + 1})
    return ranges


def audit_spot_rows(
    rows: Sequence[SpotKlineRow],
    *,
    expected_open_times: Sequence[int],
) -> dict[str, Any]:
    observed = [row.open_time_ms for row in rows]
    counts: dict[int, int] = {}
    for ts in observed:
        counts[ts] = counts.get(ts, 0) + 1
    duplicate_open_times = sorted(ts for ts, count in counts.items() if count > 1)
    unique_times = sorted(counts)
    expected_set = set(expected_open_times)
    observed_set = set(unique_times)
    missing = sorted(expected_set - observed_set)
    unexpected = sorted(observed_set - expected_set)
    is_strictly_ordered = all(
        observed[i] < observed[i + 1] for i in range(len(observed) - 1)
    )
    violations_by_row: list[dict[str, Any]] = []
    zero_volume_count = 0
    for row in rows:
        if Decimal(row.volume) == 0:
            zero_volume_count += 1
        violations = row_invariant_violations(row)
        if violations:
            violations_by_row.append(
                {"open_time_ms": row.open_time_ms, "violations": violations}
            )
    return {
        "row_count": len(rows),
        "observed_unique_open_times": len(unique_times),
        "expected_native_hours": len(expected_open_times),
        "duplicate_open_times": duplicate_open_times,
        "duplicate_count": len(duplicate_open_times),
        "missing_open_time_ranges_ms": compress_to_ranges(missing, BAR_MS),
        "missing_count": len(missing),
        "unexpected_open_times": unexpected,
        "is_strictly_ordered_by_open_time": is_strictly_ordered,
        "invariant_violation_count": len(violations_by_row),
        "invariant_violations_head": violations_by_row[:20],
        "zero_volume_count": zero_volume_count,
        "first_open_time_ms": observed[0] if observed else None,
        "last_open_time_ms": observed[-1] if observed else None,
        "first_open_time_utc": iso_utc_from_ms(observed[0]) if observed else None,
        "last_open_time_utc": iso_utc_from_ms(observed[-1]) if observed else None,
        "schema_ok": all(len(row_invariant_violations(row)) == 0 for row in rows)
        and not duplicate_open_times,
    }


def canonical_jsonl_bytes(rows: Sequence[SpotKlineRow]) -> bytes:
    lines = [
        json.dumps(row.canonical_dict(), sort_keys=True, separators=(",", ":"))
        for row in rows
    ]
    text = "\n".join(lines)
    if lines:
        text += "\n"
    return text.encode("utf-8")


def build_spot_identity_payload(
    *,
    source_object_identities: list[dict[str, Any]],
    canonical_klines_sha256: str,
    canonical_row_count: int,
    gap_count: int,
    duplicate_count: int,
    construction_code_sha256: Mapping[str, str],
    provenance_git_commit_sha: str,
) -> dict[str, Any]:
    return {
        "canonical_klines_sha256": canonical_klines_sha256,
        "canonical_row_count": canonical_row_count,
        "construction_code_sha256": dict(sorted(construction_code_sha256.items())),
        "dataset_id": DATASET_ID,
        "documented_api_origin": DOCUMENTED_API_ORIGIN,
        "duplicate_count": duplicate_count,
        "duplicate_policy": DUPLICATE_POLICY,
        "end_exclusive": END_EXCLUSIVE,
        "exchange": VENUE,
        "gap_count": gap_count,
        "gap_policy": GAP_POLICY,
        "interval": INTERVAL,
        "market_type": MARKET_TYPE,
        "market_03_scientifically_bound": False,
        "normalization_rules": list(NORMALIZATION_RULES),
        "protected_oos_excluded": True,
        "provenance_git_commit_sha": provenance_git_commit_sha,
        "provider": PROVIDER,
        "source_archive_root": ARCHIVE_ROOT,
        "source_object_identities": source_object_identities,
        "start_inclusive": START_INCLUSIVE,
        "symbol": SYMBOL,
    }


def snapshot_from_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    snapshot_id = sha256_of_canonical_identity_payload(payload)
    return {"identity_payload": payload, "snapshot_id": snapshot_id}


@dataclass(frozen=True)
class FundingRecord:
    time_ms: int
    rate: str
    source: str

    def rate_decimal(self) -> Decimal:
        return Decimal(self.rate)


def parse_vision_funding_csv(text: str) -> tuple[list[FundingRecord], dict[str, Any]]:
    text = _strip_bom(text)
    rows_raw = list(csv.reader(io.StringIO(text)))
    header_present = False
    if rows_raw and rows_raw[0] and rows_raw[0][0].strip().lower() in {
        "calc_time", "calctime", "calc time",
    }:
        header_present = True
        rows_raw = rows_raw[1:]
    parsed: list[FundingRecord] = []
    malformed = 0
    for raw in rows_raw:
        if not raw or len(raw) < 3:
            malformed += 1
            continue
        try:
            time_ms = int(raw[0])
            if time_ms >= PROTECTED_OOS_START_MS:
                continue
            rate = raw[2]
            _finite_decimal(rate, "last_funding_rate")
        except (InvalidOperation, ValueError):
            malformed += 1
            continue
        parsed.append(FundingRecord(time_ms=time_ms, rate=rate, source="vision_last_funding_rate"))
    meta = {
        "header_present": header_present,
        "raw_row_count": len(rows_raw),
        "malformed_row_count": malformed,
        "protected_oos_rows_skipped_uninspected": None,
    }
    return parsed, meta


def parse_rest_funding_records(payload: Sequence[Mapping[str, Any]]) -> list[FundingRecord]:
    records: list[FundingRecord] = []
    for item in payload:
        time_ms = int(item["fundingTime"])
        if time_ms >= PROTECTED_OOS_START_MS:
            continue
        rate = str(item["fundingRate"])
        _finite_decimal(rate, "fundingRate")
        records.append(
            FundingRecord(time_ms=time_ms, rate=rate, source="rest_fundingRate")
        )
    return records


def funding_time_bucket_ms(time_ms: int) -> int:
    """Hour-floor used only to compare REST ms residuals vs Vision calc_time.

    Not a publication-latency claim.
    """
    return (time_ms // BAR_MS) * BAR_MS


def compare_funding_records(
    rest_records: Sequence[FundingRecord],
    vision_records: Sequence[FundingRecord],
) -> dict[str, Any]:
    rest_by_time = {row.time_ms: row for row in rest_records}
    vision_by_time = {row.time_ms: row for row in vision_records}
    rest_times = set(rest_by_time)
    vision_times = set(vision_by_time)
    exact_time_overlap = sorted(rest_times & vision_times)
    exact_rate_equal = 0
    exact_rate_mismatch_head: list[dict[str, Any]] = []
    for ts in exact_time_overlap:
        rest_rate = rest_by_time[ts].rate_decimal()
        vision_rate = vision_by_time[ts].rate_decimal()
        if rest_rate == vision_rate:
            exact_rate_equal += 1
        elif len(exact_rate_mismatch_head) < 10:
            exact_rate_mismatch_head.append(
                {
                    "time_ms": ts,
                    "time_utc": iso_utc_from_ms(ts),
                    "rest_fundingRate": rest_by_time[ts].rate,
                    "vision_last_funding_rate": vision_by_time[ts].rate,
                }
            )

    rest_by_hour = {}
    rest_ms_residual = 0
    for row in rest_records:
        hour = funding_time_bucket_ms(row.time_ms)
        rest_by_hour[hour] = row
        if row.time_ms != hour:
            rest_ms_residual += 1
    vision_by_hour = {}
    vision_ms_residual = 0
    for row in vision_records:
        hour = funding_time_bucket_ms(row.time_ms)
        vision_by_hour[hour] = row
        if row.time_ms != hour:
            vision_ms_residual += 1
    hour_overlap = sorted(set(rest_by_hour) & set(vision_by_hour))
    hour_rate_equal = 0
    hour_rate_mismatch_head: list[dict[str, Any]] = []
    for hour in hour_overlap:
        if rest_by_hour[hour].rate_decimal() == vision_by_hour[hour].rate_decimal():
            hour_rate_equal += 1
        elif len(hour_rate_mismatch_head) < 10:
            hour_rate_mismatch_head.append(
                {
                    "hour_ms": hour,
                    "rest_time_ms": rest_by_hour[hour].time_ms,
                    "vision_time_ms": vision_by_hour[hour].time_ms,
                    "rest_fundingRate": rest_by_hour[hour].rate,
                    "vision_last_funding_rate": vision_by_hour[hour].rate,
                }
            )

    rest_only = sorted(rest_times - vision_times)
    vision_only = sorted(vision_times - rest_times)
    rest_monotonic = all(
        rest_records[i].time_ms < rest_records[i + 1].time_ms
        for i in range(len(rest_records) - 1)
    ) if len(rest_records) > 1 else True
    vision_monotonic = all(
        vision_records[i].time_ms < vision_records[i + 1].time_ms
        for i in range(len(vision_records) - 1)
    ) if len(vision_records) > 1 else True

    semantic_equivalent = (
        hour_overlap
        and hour_rate_equal == len(hour_overlap)
        and not hour_rate_mismatch_head
    )
    return {
        "rest_row_count": len(rest_records),
        "vision_row_count": len(vision_records),
        "rest_first_time_utc": iso_utc_from_ms(rest_records[0].time_ms) if rest_records else None,
        "rest_last_time_utc": iso_utc_from_ms(rest_records[-1].time_ms) if rest_records else None,
        "vision_first_time_utc": (
            iso_utc_from_ms(vision_records[0].time_ms) if vision_records else None
        ),
        "vision_last_time_utc": (
            iso_utc_from_ms(vision_records[-1].time_ms) if vision_records else None
        ),
        "rest_monotonic_fundingTime": rest_monotonic,
        "vision_monotonic_calc_time": vision_monotonic,
        "exact_timestamp_overlap_count": len(exact_time_overlap),
        "exact_timestamp_rate_equal_count": exact_rate_equal,
        "exact_timestamp_rate_mismatch_count": len(exact_time_overlap) - exact_rate_equal,
        "exact_timestamp_rate_mismatch_head": exact_rate_mismatch_head,
        "rest_nonzero_ms_residual_count": rest_ms_residual,
        "vision_nonzero_ms_residual_count": vision_ms_residual,
        "hour_bucket_overlap_count": len(hour_overlap),
        "hour_bucket_rate_equal_count": hour_rate_equal,
        "hour_bucket_rate_mismatch_count": len(hour_overlap) - hour_rate_equal,
        "hour_bucket_rate_mismatch_head": hour_rate_mismatch_head,
        "rest_times_absent_from_vision_count": len(rest_only),
        "vision_times_absent_from_rest_count": len(vision_only),
        "semantic_rate_equivalence_on_hour_buckets": semantic_equivalent,
        "not_the_same_frozen_object": True,
        "rest_field": "fundingRate",
        "rest_timestamp_field": "fundingTime",
        "vision_field": "last_funding_rate",
        "vision_timestamp_field": "calc_time",
        "protected_oos_compared": False,
    }


def audit_funding_records(records: Sequence[FundingRecord]) -> dict[str, Any]:
    times = [row.time_ms for row in records]
    counts: dict[int, int] = {}
    for ts in times:
        counts[ts] = counts.get(ts, 0) + 1
    duplicates = sorted(ts for ts, count in counts.items() if count > 1)
    non_finite = 0
    for row in records:
        try:
            value = row.rate_decimal()
            if not value.is_finite():
                non_finite += 1
        except InvalidOperation:
            non_finite += 1
    monotonic = all(times[i] < times[i + 1] for i in range(len(times) - 1)) if len(times) > 1 else True
    return {
        "row_count": len(records),
        "duplicate_timestamp_count": len(duplicates),
        "non_finite_rate_count": non_finite,
        "monotonic_time": monotonic,
        "first_time_utc": iso_utc_from_ms(times[0]) if times else None,
        "last_time_utc": iso_utc_from_ms(times[-1]) if times else None,
    }


def extract_b2_06_funding_container_hashes(
    ledger: Mapping[str, Any],
) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for obj in ledger.get("objects", []):
        if obj.get("series") != "funding":
            continue
        period = obj.get("period")
        if not period:
            continue
        start_ms = obj.get("min_source_timestamp_ms")
        if isinstance(start_ms, int) and start_ms >= PROTECTED_OOS_START_MS:
            continue
        out[period] = {
            "archive_object_name": obj.get("archive_object_name"),
            "container_sha256": obj.get("container_sha256"),
            "container_bytes": obj.get("container_bytes"),
            "member_sha256": obj.get("member_sha256"),
            "member_bytes": obj.get("member_bytes"),
            "parsed_row_count": obj.get("parsed_row_count"),
            "zip_url": obj.get("zip_url"),
            "checksum_verification": obj.get("checksum_verification"),
        }
    return out


def compare_vision_zips_to_b2_06(
    local_identities: Sequence[Mapping[str, Any]],
    b2_06_by_period: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    compared = []
    hash_equal = 0
    hash_mismatch = 0
    missing_in_b2_06 = 0
    missing_local = 0
    for local in local_identities:
        period = local["period"]
        remote = b2_06_by_period.get(period)
        if remote is None:
            missing_in_b2_06 += 1
            compared.append(
                {
                    "period": period,
                    "status": "NOT_IN_B2_06_LEDGER",
                    "local_container_sha256": local.get("container_sha256"),
                }
            )
            continue
        equal = local.get("container_sha256") == remote.get("container_sha256")
        if equal:
            hash_equal += 1
            status = "CONTAINER_SHA256_EQUAL"
        else:
            hash_mismatch += 1
            status = "CONTAINER_SHA256_MISMATCH"
        compared.append(
            {
                "period": period,
                "status": status,
                "local_container_sha256": local.get("container_sha256"),
                "b2_06_container_sha256": remote.get("container_sha256"),
                "local_bytes": local.get("container_bytes"),
                "b2_06_bytes": remote.get("container_bytes"),
            }
        )
    b2_06_periods = set(b2_06_by_period)
    local_periods = {row["period"] for row in local_identities}
    for period in sorted(b2_06_periods - local_periods):
        missing_local += 1
        compared.append(
            {
                "period": period,
                "status": "B2_06_PERIOD_NOT_REDOWNLOADED",
                "b2_06_container_sha256": b2_06_by_period[period].get("container_sha256"),
            }
        )
    return {
        "b2_06_dataset_id": B2_06_DATASET_ID,
        "b2_06_snapshot_id": B2_06_SNAPSHOT_ID,
        "compared_period_count": len(local_identities),
        "container_sha256_equal_count": hash_equal,
        "container_sha256_mismatch_count": hash_mismatch,
        "local_not_in_b2_06_count": missing_in_b2_06,
        "b2_06_not_redownloaded_count": missing_local,
        "all_overlapping_containers_byte_identical": (
            hash_mismatch == 0 and hash_equal > 0
        ),
        "periods": compared,
        "b2_06_research_authorized": False,
        "b2_06_execution_authorized_by_this_unit": False,
    }


def rest_funding_query_bounds() -> dict[str, Any]:
    start = datetime.fromisoformat(FUNDING_REST_START_INCLUSIVE.replace("Z", "+00:00"))
    end = datetime.fromisoformat(FUNDING_COMPARE_END_EXCLUSIVE.replace("Z", "+00:00"))
    start_ms = int(start.timestamp() * 1000)
    end_ms = int(end.timestamp() * 1000)
    return {
        "endpoint": FUNDING_REST_ENDPOINT,
        "fallback_endpoint": FUNDING_REST_FALLBACK_ENDPOINT,
        "path": FUNDING_REST_PATH,
        "symbol": FUNDING_SYMBOL,
        "startTime_ms": start_ms,
        "endTime_exclusive_ms": end_ms,
        "endTime_inclusive_ms": end_ms - 1,
        "limit": 1000,
        "protected_oos_excluded": True,
    }


FORBIDDEN_STRATEGY_TOKENS = (
    "ema600",
    "funding_pct",
    "funding_3d",
    "equity_curve",
    "cagr",
    "sharpe",
    "sortino",
)


def assert_no_strategy_quantities(namespace: Iterable[str]) -> None:
    lowered = {name.lower() for name in namespace}
    for token in FORBIDDEN_STRATEGY_TOKENS:
        if token in lowered:
            raise Market03SpotDatasetError(
                f"forbidden MARKET-03 strategy quantity present: {token}"
            )
