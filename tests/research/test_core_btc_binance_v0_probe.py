"""Deterministic, network-free tests for the CORE_BTC_BINANCE_V0 source
probe. No test here touches Binance or any other network endpoint -- every
fixture is a local synthetic ZIP/CSV/checksum built in `tmp_path`."""
from __future__ import annotations

import asyncio
import io
import json
import zipfile
from decimal import Decimal
from pathlib import Path

import pytest

import scripts.research.core_btc_binance_v0_probe as probe_cli
from scripts.research.core_btc_binance_v0_probe_lib import (
    BAR_MS,
    CoreBtcBinanceV0ProbeError,
    KlineRow,
    archive_urls,
    audit_klines,
    bar_end_exclusive_ms,
    compress_to_ranges,
    decide_existing_zip_disposition,
    evaluate_month_pass,
    expected_bucket_starts,
    local_checksum_filename,
    local_zip_filename,
    month_bounds_ms,
    parse_checksum_text,
    parse_kline_csv,
    read_kline_csv_member,
    sha256_of_bytes,
    sha256_of_file,
    validate_year_month,
)

SYMBOL_INTERVAL = "BTCUSDT-1m"


def _row_line(open_time_ms, *, open_="50000", high="50100", low="49900", close="50050",
              volume="12.5", close_time_ms=None, quote_volume="625000", count="1000",
              taker_buy_base="6.25", taker_buy_quote="312500", ignore="0"):
    if close_time_ms is None:
        close_time_ms = open_time_ms + BAR_MS - 1
    return ",".join(str(x) for x in (
        open_time_ms, open_, high, low, close, volume, close_time_ms, quote_volume, count,
        taker_buy_base, taker_buy_quote, ignore))


def _valid_month_csv(year_month: str, n_rows: int, *, header: bool = False) -> str:
    start_ms, _ = month_bounds_ms(year_month)
    lines = []
    if header:
        lines.append("open_time,open,high,low,close,volume,close_time,quote_volume,count,"
                      "taker_buy_base,taker_buy_quote,ignore")
    for i in range(n_rows):
        lines.append(_row_line(start_ms + i * BAR_MS))
    return "\n".join(lines) + "\n"


def _make_zip_bytes(year_month: str, csv_text: str, *, member_name: str = None) -> bytes:
    member_name = member_name or f"{SYMBOL_INTERVAL}-{year_month}.csv"
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr(member_name, csv_text)
    return buf.getvalue()


def _checksum_text(sha256_hex: str, filename: str) -> str:
    return f"{sha256_hex}  {filename}\n"


# ---------------------------------------------------------------------------
# 1. deterministic archive/checksum URL construction
# ---------------------------------------------------------------------------
def test_archive_urls_are_deterministic_and_match_the_contract_root():
    zip_url, checksum_url = archive_urls("2020-01")
    assert zip_url == (
        "https://data.binance.vision/data/futures/um/monthly/klines/"
        "BTCUSDT/1m/BTCUSDT-1m-2020-01.zip")
    assert checksum_url == zip_url + ".CHECKSUM"
    # deterministic: calling again gives byte-identical output
    assert archive_urls("2020-01") == (zip_url, checksum_url)


def test_archive_urls_rejects_malformed_year_month():
    for bad in ("2020-13", "2020-1", "20-01", "not-a-month", "2020-00"):
        with pytest.raises(CoreBtcBinanceV0ProbeError):
            validate_year_month(bad)


# ---------------------------------------------------------------------------
# 2/3/4. checksum verification / mismatch / malformed
# ---------------------------------------------------------------------------
def test_valid_checksum_verification_passes():
    data = b"hello binance archive"
    digest = sha256_of_bytes(data)
    parsed = parse_checksum_text(_checksum_text(digest, "BTCUSDT-1m-2020-01.zip"))
    assert parsed["sha256"] == digest
    assert parsed["filename"] == "BTCUSDT-1m-2020-01.zip"


def test_checksum_mismatch_is_rejected_via_audit_local(tmp_path: Path):
    year_month = "2021-05"
    csv_text = _valid_month_csv(year_month, 3)
    zip_bytes = _make_zip_bytes(year_month, csv_text)
    (tmp_path / local_zip_filename(year_month)).write_bytes(zip_bytes)
    wrong_digest = sha256_of_bytes(b"not the real archive bytes")
    (tmp_path / local_checksum_filename(year_month)).write_text(
        _checksum_text(wrong_digest, local_zip_filename(year_month)), encoding="utf-8")

    report = probe_cli.run_audit_local(tmp_path, [year_month])
    record = report["months"][0]
    assert record["checksum_verification"] == "MISMATCH"
    assert record["month_passed"] is False  # a mismatch must never receive verified source status


def test_malformed_checksum_is_rejected():
    with pytest.raises(CoreBtcBinanceV0ProbeError):
        parse_checksum_text("not-a-sha256  BTCUSDT-1m-2020-01.zip")
    with pytest.raises(CoreBtcBinanceV0ProbeError):
        parse_checksum_text("")


def test_malformed_checksum_via_audit_local_is_not_verifiable(tmp_path: Path):
    year_month = "2021-05"
    csv_text = _valid_month_csv(year_month, 3)
    zip_bytes = _make_zip_bytes(year_month, csv_text)
    (tmp_path / local_zip_filename(year_month)).write_bytes(zip_bytes)
    (tmp_path / local_checksum_filename(year_month)).write_text("garbage not a checksum", encoding="utf-8")

    report = probe_cli.run_audit_local(tmp_path, [year_month])
    record = report["months"][0]
    assert record["checksum_verification"] == "NOT_VERIFIABLE_MISSING_CHECKSUM"
    assert record["expected_sha256_status"].startswith("MALFORMED")
    assert record["month_passed"] is False


# ---------------------------------------------------------------------------
# 5/6. kline parsing (12-column, optional header)
# ---------------------------------------------------------------------------
def test_valid_12_column_kline_parsing():
    rows, meta = parse_kline_csv(_valid_month_csv("2021-05", 5))
    assert len(rows) == 5
    assert meta["header_present"] is False
    assert meta["malformed_row_count"] == 0
    assert isinstance(rows[0], KlineRow)
    assert rows[0].open == Decimal("50000")
    assert rows[0].trade_count == 1000


def test_optional_header_row_is_handled():
    rows, meta = parse_kline_csv(_valid_month_csv("2021-05", 4, header=True))
    assert meta["header_present"] is True
    assert len(rows) == 4  # header row itself never mistaken for a data row


# ---------------------------------------------------------------------------
# 7/8. duplicate / missing-interval detection
# ---------------------------------------------------------------------------
def test_duplicate_timestamp_detection():
    year_month = "2021-05"
    start_ms, _ = month_bounds_ms(year_month)
    rows = [
        KlineRow(start_ms, Decimal("1"), Decimal("2"), Decimal("1"), Decimal("1"), Decimal("1"),
                 start_ms + BAR_MS - 1, Decimal("1"), 1, Decimal("0"), Decimal("0")),
        KlineRow(start_ms, Decimal("1"), Decimal("2"), Decimal("1"), Decimal("1"), Decimal("1"),
                 start_ms + BAR_MS - 1, Decimal("1"), 1, Decimal("0"), Decimal("0")),
    ]
    audit = audit_klines(rows, year_month, malformed_row_count=0)
    assert audit["duplicate_count"] == 1
    assert audit["duplicate_open_times"] == [start_ms]


def test_missing_1m_interval_detection_reports_exact_range():
    year_month = "2021-05"
    start_ms, _ = month_bounds_ms(year_month)

    def _row(open_time_ms):
        return KlineRow(open_time_ms, Decimal("1"), Decimal("2"), Decimal("1"), Decimal("1"),
                         Decimal("1"), open_time_ms + BAR_MS - 1, Decimal("1"), 1,
                         Decimal("0"), Decimal("0"))

    # minutes 0,1 present, 2,3 missing, 4 present
    rows = [_row(start_ms), _row(start_ms + BAR_MS), _row(start_ms + 4 * BAR_MS)]
    audit = audit_klines(rows, year_month, malformed_row_count=0)
    missing_gap = [start_ms + 2 * BAR_MS, start_ms + 3 * BAR_MS]
    assert missing_gap in audit["missing_open_time_ranges_ms"]
    # the rest of the month (after minute 4) is also missing -- just confirm this
    # specific small gap is reported exactly, not merged/lost among the rest.
    assert audit["missing_bucket_count"] >= 2


def test_compress_to_ranges_merges_contiguous_and_splits_gaps():
    values = [0, 60_000, 120_000, 300_000, 360_000]
    assert compress_to_ranges(values, BAR_MS) == [[0, 120_000], [300_000, 360_000]]
    assert compress_to_ranges([], BAR_MS) == []


# ---------------------------------------------------------------------------
# 9. malformed numeric row
# ---------------------------------------------------------------------------
def test_malformed_numeric_row_is_counted_and_excluded():
    year_month = "2021-05"
    start_ms, _ = month_bounds_ms(year_month)
    good = _row_line(start_ms)
    bad = _row_line(start_ms + BAR_MS, open_="NOT_A_NUMBER")
    text = good + "\n" + bad + "\n"
    rows, meta = parse_kline_csv(text)
    assert len(rows) == 1
    assert meta["malformed_row_count"] == 1
    assert meta["malformed_row_indices"] == [1]


def test_short_row_is_malformed():
    rows, meta = parse_kline_csv("1,2,3\n")
    assert rows == []
    assert meta["malformed_row_count"] == 1


# ---------------------------------------------------------------------------
# 10/11. OHLC invariant / taker-buy > total-volume violations
# ---------------------------------------------------------------------------
def test_ohlc_invariant_violation_is_reported():
    year_month = "2021-05"
    start_ms, _ = month_bounds_ms(year_month)
    # high < close is impossible for a valid bar
    bad_row = KlineRow(start_ms, Decimal("100"), Decimal("100"), Decimal("90"), Decimal("110"),
                        Decimal("1"), start_ms + BAR_MS - 1, Decimal("1"), 1,
                        Decimal("0"), Decimal("0"))
    audit = audit_klines([bad_row], year_month, malformed_row_count=0)
    assert audit["invariant_violation_count"] == 1
    assert "high_lt_max_open_close" in audit["invariant_violations"][0]["violations"]


def test_taker_buy_exceeds_total_volume_violation_is_reported():
    year_month = "2021-05"
    start_ms, _ = month_bounds_ms(year_month)
    bad_row = KlineRow(start_ms, Decimal("100"), Decimal("110"), Decimal("90"), Decimal("105"),
                        Decimal("1"), start_ms + BAR_MS - 1, Decimal("1"), 1,
                        Decimal("5"), Decimal("0"))  # taker_buy_base 5 > base_volume 1
    audit = audit_klines([bad_row], year_month, malformed_row_count=0)
    assert "taker_buy_base_volume_exceeds_total" in audit["invariant_violations"][0]["violations"]


def test_close_time_before_open_time_is_flagged():
    year_month = "2021-05"
    start_ms, _ = month_bounds_ms(year_month)
    bad_row = KlineRow(start_ms, Decimal("100"), Decimal("110"), Decimal("90"), Decimal("105"),
                        Decimal("1"), start_ms - 1, Decimal("1"), 1, Decimal("0"), Decimal("0"))
    audit = audit_klines([bad_row], year_month, malformed_row_count=0)
    assert "close_time_before_open_time" in audit["invariant_violations"][0]["violations"]


# ---------------------------------------------------------------------------
# 12. deterministic report ordering / serialization
# ---------------------------------------------------------------------------
def test_report_ordering_and_serialization_is_deterministic():
    report = probe_cli.run_inventory(["2024-03", "2020-01", "2026-07", "2021-05"])
    assert report["probe_months"] == ["2020-01", "2021-05", "2024-03", "2026-07"]
    assert [m["year_month"] for m in report["months"]] == report["probe_months"]

    # freeze the volatile timestamp so serialization comparisons are meaningful
    report["generated_at_utc"] = "FROZEN"
    serialized_a = probe_cli._serialize(report)
    serialized_b = probe_cli._serialize(json.loads(json.dumps(report)))
    assert serialized_a == serialized_b
    # top-level keys must serialize in sorted order
    parsed = json.loads(serialized_a)
    assert sorted(parsed.keys()) == list(parsed.keys())


def test_report_has_schema_version_and_does_not_claim_acceptance():
    report = probe_cli.run_inventory(["2020-01"])
    assert report["schema_version"] == 1
    assert "NOT" in report["dataset_acceptance_note"]
    assert "DATASET_ACCEPTED" in report["dataset_acceptance_note"]


# ---------------------------------------------------------------------------
# 13/14. existing-file reuse vs conflicting-revision fail-closed
# ---------------------------------------------------------------------------
def test_existing_identical_file_is_reused():
    digest = sha256_of_bytes(b"same bytes")
    assert decide_existing_zip_disposition(digest, digest) == "REUSED_IDENTICAL"


def test_existing_file_with_no_reference_checksum_is_reused_unverified():
    digest = sha256_of_bytes(b"some bytes")
    assert decide_existing_zip_disposition(digest, None) == "REUSED_UNVERIFIED_NO_REFERENCE"


def test_new_file_with_no_existing_local_copy():
    assert decide_existing_zip_disposition(None, "irrelevant") == "NEW"
    assert decide_existing_zip_disposition(None, None) == "NEW"


def test_existing_conflicting_revision_fails_closed_and_does_not_destroy_old_bytes(tmp_path: Path):
    existing_digest = sha256_of_bytes(b"old revision bytes")
    expected_digest = sha256_of_bytes(b"a materially different upstream revision")
    assert existing_digest != expected_digest
    assert decide_existing_zip_disposition(existing_digest, expected_digest) == "REVISION_CONFLICT"

    # end-to-end through the async probe pipeline with a faked network layer:
    # an on-disk zip that disagrees with the freshly-fetched checksum must be
    # left byte-for-byte untouched, never silently overwritten.
    year_month = "2021-05"
    old_bytes = b"old revision bytes"
    zip_path = tmp_path / local_zip_filename(year_month)
    zip_path.write_bytes(old_bytes)

    async def _fake_fetch(session, url, timeout_seconds):
        if url.endswith(".CHECKSUM"):
            text = _checksum_text(expected_digest, local_zip_filename(year_month))
            return text.encode("utf-8"), "HTTP_200"
        raise AssertionError("must not re-fetch the zip body when an existing file conflicts")

    orig_fetch = probe_cli._fetch
    probe_cli._fetch = _fake_fetch
    try:
        report = asyncio.run(probe_cli._run_probe_async(tmp_path, [year_month], 5.0))
    finally:
        probe_cli._fetch = orig_fetch

    record = report["months"][0]
    assert record["source_status"] == "REVISION_CONFLICT"
    assert record["month_passed"] is False
    assert zip_path.read_bytes() == old_bytes  # old revision preserved, never destroyed


def test_existing_identical_file_is_reused_end_to_end_through_probe_pipeline(tmp_path: Path):
    year_month = "2021-05"
    csv_text = _valid_month_csv(year_month, 3)
    zip_bytes = _make_zip_bytes(year_month, csv_text)
    zip_path = tmp_path / local_zip_filename(year_month)
    zip_path.write_bytes(zip_bytes)
    digest = sha256_of_bytes(zip_bytes)

    async def _fake_fetch(session, url, timeout_seconds):
        if url.endswith(".CHECKSUM"):
            text = _checksum_text(digest, local_zip_filename(year_month))
            return text.encode("utf-8"), "HTTP_200"
        raise AssertionError("must not re-download an already-verified-identical file")

    orig_fetch = probe_cli._fetch
    probe_cli._fetch = _fake_fetch
    try:
        report = asyncio.run(probe_cli._run_probe_async(tmp_path, [year_month], 5.0))
    finally:
        probe_cli._fetch = orig_fetch

    record = report["months"][0]
    assert record["source_status"] == "REUSED_IDENTICAL"
    assert record["checksum_verification"] == "VERIFIED"
    assert record["observed_rows"] == 3


# ---------------------------------------------------------------------------
# no-lookahead / availability helper
# ---------------------------------------------------------------------------
def test_bar_end_exclusive_never_uses_close_time():
    assert bar_end_exclusive_ms(0) == BAR_MS
    assert bar_end_exclusive_ms(1_600_000_000_000) == 1_600_000_000_000 + BAR_MS


def test_expected_bucket_starts_matches_calendar_month_length():
    # 2021-05 has 31 days
    assert len(expected_bucket_starts("2021-05")) == 31 * 24 * 60
    # 2020-02 is a leap-year February: 29 days
    assert len(expected_bucket_starts("2020-02")) == 29 * 24 * 60


# ---------------------------------------------------------------------------
# month_passed policy
# ---------------------------------------------------------------------------
def test_evaluate_month_pass_requires_verification_and_clean_audit():
    good = {
        "source_status": "HTTP_200", "checksum_verification": "VERIFIED", "parser_status": "OK",
        "malformed_row_count": 0, "duplicate_count": 0, "invariant_violation_count": 0,
        "is_strictly_ordered_by_open_time": True,
    }
    assert evaluate_month_pass(good) is True
    assert evaluate_month_pass({**good, "checksum_verification": "MISMATCH"}) is False
    assert evaluate_month_pass({**good, "duplicate_count": 1}) is False
    assert evaluate_month_pass({**good, "missing_bucket_count": 500}) is True  # gaps alone don't fail


# ---------------------------------------------------------------------------
# zip member reading / unexpected archive shape
# ---------------------------------------------------------------------------
def test_read_kline_csv_member_handles_missing_file(tmp_path: Path):
    text, names, status = read_kline_csv_member(tmp_path / "does-not-exist.zip", "2021-05")
    assert status == "NO_SUCH_FILE"
    assert text is None


def test_read_kline_csv_member_flags_corrupt_zip_bytes(tmp_path: Path):
    bad_zip = tmp_path / "corrupt.zip"
    bad_zip.write_bytes(b"this is not a zip file at all")
    text, names, status = read_kline_csv_member(bad_zip, "2021-05")
    assert status == "BAD_ZIP_FILE"
    assert text is None


def test_read_kline_csv_member_flags_unexpected_zip_shape(tmp_path: Path):
    zip_path = tmp_path / "weird.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("readme.txt", "not a kline file")
        zf.writestr("other.csv", "1,2,3\n")
        zf.writestr("another.csv", "4,5,6\n")
    text, names, status = read_kline_csv_member(zip_path, "2021-05")
    assert status == "UNEXPECTED_ZIP_MEMBERS"
    assert text is None
    assert set(names) == {"readme.txt", "other.csv", "another.csv"}


def test_audit_local_reports_no_local_file_without_network(tmp_path: Path):
    report = probe_cli.run_audit_local(tmp_path, ["2021-05"])
    record = report["months"][0]
    assert record["source_status"] == "NO_LOCAL_FILE"
    assert record["month_passed"] is False
