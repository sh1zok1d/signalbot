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
    evaluate_checksum_verification,
    evaluate_local_audit_pass,
    evaluate_month_pass,
    expected_bucket_starts,
    expected_csv_member_name,
    local_checksum_filename,
    local_zip_filename,
    month_bounds_ms,
    parse_checksum_text,
    parse_kline_csv,
    read_kline_csv_member,
    row_invariant_violations,
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


def _kline_row(open_time_ms: int, **overrides) -> KlineRow:
    defaults = dict(
        open_time_ms=open_time_ms, open=Decimal("50000"), high=Decimal("50100"),
        low=Decimal("49900"), close=Decimal("50050"), base_volume=Decimal("12.5"),
        close_time_ms=open_time_ms + BAR_MS - 1, quote_volume=Decimal("625000"),
        trade_count=1000, taker_buy_base_volume=Decimal("6.25"),
        taker_buy_quote_volume=Decimal("312500"))
    defaults.update(overrides)
    return KlineRow(**defaults)


def _record_from_audit(year_month: str, rows, *, malformed_row_count: int = 0,
                        source_status: str = "HTTP_200") -> dict:
    """Build a full month-record dict the way the CLI would, directly from
    an `audit_klines()` result, without needing a real zip/CSV round trip --
    for exercising `evaluate_month_pass`/`evaluate_local_audit_pass` against
    many completeness scenarios quickly."""
    record = {
        "year_month": year_month,
        "source_status": source_status,
        "checksum_verification": "VERIFIED",
        "parser_status": "OK",
    }
    record.update(audit_klines(rows, year_month, malformed_row_count))
    return record


def _full_month_csv(year_month: str) -> str:
    """A real, complete calendar month of consecutive valid 1m rows. Used
    sparingly (Feb of a non-leap year is the smallest real month, 40,320
    rows) for the few tests that need a genuine end-to-end zip/CSV/audit
    round trip rather than directly constructed KlineRows."""
    starts = expected_bucket_starts(year_month)
    return "\n".join(_row_line(s) for s in starts) + "\n"


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
    assert report["schema_version"] == 2
    assert "NOT" in report["dataset_acceptance_note"]
    assert "DATASET_ACCEPTED" in report["dataset_acceptance_note"]


def test_report_includes_provenance_and_identity_fields():
    report = probe_cli.run_inventory(["2020-01"], git_commit_sha="deadbeef")
    assert report["provenance_git_commit_sha"] == "deadbeef"
    assert report["probe_tool_version"] == 2
    assert "month_pass_predicate_version" in report
    record = report["months"][0]
    assert record["expected_zip_filename"] == "BTCUSDT-1m-2020-01.zip"
    assert record["expected_csv_member_name"] == "BTCUSDT-1m-2020-01.csv"


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
    # RT-05: plant a pre-existing checksum sidecar too -- it belongs to the
    # OLD revision's identity just as much as the zip does, and a naive
    # "write the freshly fetched checksum first" ordering would have
    # clobbered it before the zip conflict was ever detected.
    checksum_path = tmp_path / local_checksum_filename(year_month)
    old_checksum_text = _checksum_text(sha256_of_bytes(old_bytes), local_zip_filename(year_month))
    checksum_path.write_text(old_checksum_text, encoding="utf-8")

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
    assert checksum_path.read_text(encoding="utf-8") == old_checksum_text  # sidecar preserved too


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
# RT-01: month_passed/local_audit_passed require exact calendar completeness
# ---------------------------------------------------------------------------
def test_evaluate_month_pass_requires_full_calendar_completeness():
    """Replaces the pre-red-team version of this test, which asserted that
    `missing_bucket_count=500` still passes -- that was self-confirmation of
    the exact bug the red-team found (an empty/partial CSV could reach
    SOURCE_PROBE_PASSED). For THIS four-month source-capability probe, any
    gap fails closed; the later full-dataset contract's tolerance for
    genuine historical gaps (docs/CORE_BTC_BINANCE_V0_CONTRACT.md section
    12) is a separate, later question this probe does not answer."""
    year_month = "2021-02"  # 28-day Feb: the smallest real calendar month
    starts = expected_bucket_starts(year_month)
    complete = _record_from_audit(year_month, [_kline_row(s) for s in starts])
    assert evaluate_month_pass(complete) is True

    assert evaluate_month_pass({**complete, "checksum_verification": "MISMATCH"}) is False
    assert evaluate_month_pass({**complete, "duplicate_count": 1}) is False
    assert evaluate_month_pass({**complete, "missing_bucket_count": 1}) is False
    assert evaluate_month_pass({**complete, "rows_outside_month_bounds": [123]}) is False
    assert evaluate_month_pass({**complete, "source_status": "HTTP_404"}) is False
    assert evaluate_month_pass({**complete, "observed_unique_open_times": complete["expected_rows"] - 1}) is False
    assert evaluate_month_pass({**complete, "first_open_time_ms": complete["first_open_time_ms"] + 1}) is False
    assert evaluate_month_pass({**complete, "last_open_time_ms": complete["last_open_time_ms"] - 1}) is False


def test_rt01_empty_csv_never_passes():
    record = _record_from_audit("2021-02", [])
    assert evaluate_month_pass(record) is False
    assert evaluate_local_audit_pass({**record, "source_status": "LOCAL_FILE_PRESENT"}) is False


def test_rt01_header_only_csv_never_passes():
    # a header-only CSV parses to zero data rows -- same shape as empty
    record = _record_from_audit("2021-02", [])
    assert evaluate_month_pass(record) is False


def test_rt01_one_row_csv_never_passes():
    start_ms, _ = month_bounds_ms("2021-02")
    record = _record_from_audit("2021-02", [_kline_row(start_ms)])
    assert evaluate_month_pass(record) is False


def test_rt01_one_complete_day_in_a_month_never_passes():
    start_ms, _ = month_bounds_ms("2021-02")
    rows = [_kline_row(start_ms + i * BAR_MS) for i in range(1440)]
    record = _record_from_audit("2021-02", rows)
    assert evaluate_month_pass(record) is False


def test_rt01_all_rows_from_the_wrong_month_never_passes():
    wrong_start_ms, _ = month_bounds_ms("2021-06")
    wrong_starts = expected_bucket_starts("2021-06")
    rows = [_kline_row(wrong_start_ms + i * BAR_MS) for i in range(len(wrong_starts))]
    record = _record_from_audit("2021-05", rows)  # audited AGAINST May, built from June
    assert record["rows_outside_month_bounds"] != []
    assert evaluate_month_pass(record) is False


def test_rt01_missing_first_minute_never_passes():
    year_month = "2021-02"
    starts = expected_bucket_starts(year_month)
    rows = [_kline_row(starts[i]) for i in range(len(starts)) if i != 0]
    record = _record_from_audit(year_month, rows)
    assert record["first_open_time_ms"] != starts[0]
    assert evaluate_month_pass(record) is False


def test_rt01_missing_last_minute_never_passes():
    year_month = "2021-02"
    starts = expected_bucket_starts(year_month)
    rows = [_kline_row(starts[i]) for i in range(len(starts) - 1)]
    record = _record_from_audit(year_month, rows)
    assert record["missing_bucket_count"] == 1
    assert evaluate_month_pass(record) is False


def test_rt01_one_internal_missing_minute_never_passes():
    year_month = "2021-02"
    starts = expected_bucket_starts(year_month)
    mid = len(starts) // 2
    rows = [_kline_row(starts[i]) for i in range(len(starts)) if i != mid]
    record = _record_from_audit(year_month, rows)
    assert record["missing_bucket_count"] == 1
    assert record["first_open_time_ms"] == starts[0]
    assert record["last_open_time_ms"] == starts[-1]  # isolates the mid-month gap
    assert evaluate_month_pass(record) is False


def test_rt01_complete_valid_month_passes():
    year_month = "2021-02"
    starts = expected_bucket_starts(year_month)
    record = _record_from_audit(year_month, [_kline_row(s) for s in starts])
    assert evaluate_month_pass(record) is True
    assert evaluate_local_audit_pass({**record, "source_status": "LOCAL_FILE_PRESENT"}) is True


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
    assert status == "MISSING_EXPECTED_CSV_MEMBER"
    assert text is None
    assert set(names) == {"readme.txt", "other.csv", "another.csv"}


def test_audit_local_reports_no_local_file_without_network(tmp_path: Path):
    report = probe_cli.run_audit_local(tmp_path, ["2021-05"])
    record = report["months"][0]
    assert record["source_status"] == "NO_LOCAL_FILE"
    assert record["month_passed"] is False
    assert record["local_audit_passed"] is False


# ---------------------------------------------------------------------------
# RT-02: checksum filename identity
# ---------------------------------------------------------------------------
def test_rt02_correct_filename_verifies():
    digest = sha256_of_bytes(b"pretend zip bytes")
    expected_name = local_zip_filename("2020-01")
    parsed = parse_checksum_text(_checksum_text(digest, expected_name))
    assert evaluate_checksum_verification(digest, parsed, expected_name) == "VERIFIED"


def test_rt02_wrong_symbol_fails_identity():
    digest = sha256_of_bytes(b"pretend zip bytes")
    expected_name = local_zip_filename("2020-01")
    parsed = parse_checksum_text(_checksum_text(digest, "ETHUSDT-1m-2020-01.zip"))
    assert evaluate_checksum_verification(digest, parsed, expected_name) == "FILENAME_IDENTITY_MISMATCH"


def test_rt02_wrong_month_fails_identity():
    digest = sha256_of_bytes(b"pretend zip bytes")
    expected_name = local_zip_filename("2020-01")
    parsed = parse_checksum_text(_checksum_text(digest, "BTCUSDT-1m-2020-02.zip"))
    assert evaluate_checksum_verification(digest, parsed, expected_name) == "FILENAME_IDENTITY_MISMATCH"


def test_rt02_wrong_interval_fails_identity():
    digest = sha256_of_bytes(b"pretend zip bytes")
    expected_name = local_zip_filename("2020-01")
    parsed = parse_checksum_text(_checksum_text(digest, "BTCUSDT-5m-2020-01.zip"))
    assert evaluate_checksum_verification(digest, parsed, expected_name) == "FILENAME_IDENTITY_MISMATCH"


def test_rt02_daily_filename_fails_identity_for_monthly_object():
    digest = sha256_of_bytes(b"pretend zip bytes")
    expected_name = local_zip_filename("2020-01")
    parsed = parse_checksum_text(_checksum_text(digest, "BTCUSDT-1m-2020-01-15.zip"))
    assert evaluate_checksum_verification(digest, parsed, expected_name) == "FILENAME_IDENTITY_MISMATCH"


def test_rt02_hash_only_checksum_never_verifies():
    digest = sha256_of_bytes(b"pretend zip bytes")
    expected_name = local_zip_filename("2020-01")
    parsed = parse_checksum_text(digest)  # just the hex digest, no filename token at all
    assert parsed["filename"] == ""
    assert evaluate_checksum_verification(digest, parsed, expected_name) == "FILENAME_IDENTITY_MISMATCH"


def test_rt02_gnu_star_binary_marker_filename_is_normalized_and_passes():
    digest = sha256_of_bytes(b"pretend zip bytes")
    expected_name = local_zip_filename("2020-01")
    parsed = parse_checksum_text(f"{digest} *{expected_name}\n")
    assert parsed["filename"] == expected_name
    assert evaluate_checksum_verification(digest, parsed, expected_name) == "VERIFIED"


def test_rt02_wrong_hash_is_mismatch_regardless_of_correct_filename():
    digest = sha256_of_bytes(b"pretend zip bytes")
    wrong_digest = sha256_of_bytes(b"a different set of bytes entirely")
    expected_name = local_zip_filename("2020-01")
    parsed = parse_checksum_text(_checksum_text(wrong_digest, expected_name))
    assert evaluate_checksum_verification(digest, parsed, expected_name) == "MISMATCH"


# ---------------------------------------------------------------------------
# RT-03: exact zip member identity -- no "sole CSV fallback"
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("bad_member_name", [
    "ETHUSDT-1m-2021-05.csv",       # wrong symbol
    "BTCUSDT-5m-2021-05.csv",       # wrong interval
    "BTCUSDT-1m-2021-05-15.csv",    # daily-shaped filename, not monthly
    "folder/BTCUSDT-1m-2021-05.csv",     # path-prefixed
    "../../BTCUSDT-1m-2021-05.csv",      # path-traversal-shaped name
])
def test_rt03_wrong_member_name_is_never_accepted_even_as_sole_csv(tmp_path: Path, bad_member_name):
    zip_path = tmp_path / "adversarial.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr(bad_member_name, _valid_month_csv("2021-05", 3))
    text, names, status = read_kline_csv_member(zip_path, "2021-05")
    assert status == "MISSING_EXPECTED_CSV_MEMBER"
    assert text is None
    assert bad_member_name in names  # it's genuinely the only (or sole) CSV present -- still rejected


def test_rt03_exact_expected_member_name_is_read_directly_no_extraction(tmp_path: Path):
    zip_path = tmp_path / "good.zip"
    expected_name = expected_csv_member_name("2021-05")
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr(expected_name, _valid_month_csv("2021-05", 3))
    text, names, status = read_kline_csv_member(zip_path, "2021-05")
    assert status == "OK"
    assert text is not None
    assert names == [expected_name]


# ---------------------------------------------------------------------------
# RT-04: non-finite numerics never crash the audit
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("bad_value", ["NaN", "Infinity", "-Infinity"])
def test_rt04_non_finite_price_in_csv_is_malformed_not_crash(bad_value):
    start_ms, _ = month_bounds_ms("2021-05")
    line = _row_line(start_ms, open_=bad_value)
    rows, meta = parse_kline_csv(line + "\n")
    assert rows == []
    assert meta["malformed_row_count"] == 1


@pytest.mark.parametrize("bad_value", ["NaN", "Infinity", "-Infinity"])
def test_rt04_non_finite_volume_in_csv_is_malformed_not_crash(bad_value):
    start_ms, _ = month_bounds_ms("2021-05")
    line = _row_line(start_ms, volume=bad_value)
    rows, meta = parse_kline_csv(line + "\n")
    assert rows == []
    assert meta["malformed_row_count"] == 1


@pytest.mark.parametrize("field", [
    "open", "high", "low", "close", "base_volume", "quote_volume",
    "taker_buy_base_volume", "taker_buy_quote_volume",
])
@pytest.mark.parametrize("bad_value", [Decimal("NaN"), Decimal("Infinity"), Decimal("-Infinity")])
def test_rt04_non_finite_field_on_a_directly_constructed_row_never_crashes(field, bad_value):
    start_ms, _ = month_bounds_ms("2021-05")
    row = _kline_row(start_ms, **{field: bad_value})
    violations = row_invariant_violations(row)  # must not raise decimal.InvalidOperation
    assert f"{field}_not_finite" in violations


def test_rt04_probe_process_does_not_crash_after_a_non_finite_row(tmp_path: Path):
    """A non-finite row must not crash the WHOLE probe after files were
    already written -- audit_klines must still return a report."""
    year_month = "2021-05"
    start_ms, _ = month_bounds_ms(year_month)
    good = _row_line(start_ms)
    bad = _row_line(start_ms + BAR_MS, close="Infinity")
    rows, meta = parse_kline_csv(good + "\n" + bad + "\n")
    audit = audit_klines(rows, year_month, meta["malformed_row_count"])  # must not raise
    assert audit["observed_rows"] == 1
    assert audit["malformed_row_count"] == 1


# ---------------------------------------------------------------------------
# RT-06: audit-local is a distinct, network-free verification mode
# ---------------------------------------------------------------------------
def test_rt06_source_status_for_local_file_is_never_http_200(tmp_path: Path):
    zip_bytes = _make_zip_bytes("2021-05", _valid_month_csv("2021-05", 3))
    (tmp_path / local_zip_filename("2021-05")).write_bytes(zip_bytes)
    report = probe_cli.run_audit_local(tmp_path, ["2021-05"])
    record = report["months"][0]
    assert record["source_status"] == "LOCAL_FILE_PRESENT"
    assert record["source_status"] != "HTTP_200"


def test_rt06_overall_status_uses_local_audit_vocabulary(tmp_path: Path):
    report = probe_cli.run_audit_local(tmp_path, ["2021-05"])
    assert report["mode"] == "audit-local"
    assert report["overall_status"] == "LOCAL_AUDIT_FAILED"  # no file present, but attempted


def test_rt06_local_audit_passed_end_to_end_for_a_complete_month(tmp_path: Path):
    """A perfect local ZIP + matching checksum + complete valid month must
    be CAPABLE of a successful LOCAL audit result -- distinctly labeled,
    never pretending to be a network HTTP acquisition."""
    year_month = "2021-02"  # 28-day Feb -- smallest real month, fastest fixture
    csv_text = _full_month_csv(year_month)
    zip_bytes = _make_zip_bytes(year_month, csv_text)
    (tmp_path / local_zip_filename(year_month)).write_bytes(zip_bytes)
    digest = sha256_of_bytes(zip_bytes)
    (tmp_path / local_checksum_filename(year_month)).write_text(
        _checksum_text(digest, local_zip_filename(year_month)), encoding="utf-8")

    report = probe_cli.run_audit_local(tmp_path, [year_month])
    record = report["months"][0]
    assert record["source_status"] == "LOCAL_FILE_PRESENT"
    assert record["checksum_verification"] == "VERIFIED"
    assert record["local_audit_passed"] is True
    assert record["month_passed"] is False  # audit-local never confirms network reachability
    assert report["overall_status"] == "LOCAL_AUDIT_PASSED"


# ---------------------------------------------------------------------------
# RT-07: header/BOM detection must require known Binance header semantics
# ---------------------------------------------------------------------------
def test_rt07_standard_no_header_row_parses():
    rows, meta = parse_kline_csv(_valid_month_csv("2021-05", 3))
    assert meta["header_present"] is False
    assert len(rows) == 3


def test_rt07_explicit_supported_header_is_detected():
    rows, meta = parse_kline_csv(_valid_month_csv("2021-05", 3, header=True))
    assert meta["header_present"] is True
    assert len(rows) == 3


def test_rt07_bom_with_no_header_still_parses_first_row():
    start_ms, _ = month_bounds_ms("2021-05")
    text = "﻿" + _row_line(start_ms) + "\n"
    rows, meta = parse_kline_csv(text)
    assert meta["header_present"] is False
    assert len(rows) == 1
    assert rows[0].open_time_ms == start_ms


def test_rt07_float_timestamp_is_malformed_not_mistaken_for_a_header():
    start_ms, _ = month_bounds_ms("2021-05")
    line = _row_line(start_ms).replace(str(start_ms), f"{start_ms}.0", 1)
    rows, meta = parse_kline_csv(line + "\n")
    assert meta["header_present"] is False
    assert rows == []
    assert meta["malformed_row_count"] == 1


def test_rt07_garbage_timestamp_is_malformed_not_mistaken_for_a_header():
    rows, meta = parse_kline_csv("garbage,1,2,3,4,5,6,7,8,9,10,11\n")
    assert meta["header_present"] is False
    assert rows == []
    assert meta["malformed_row_count"] == 1


def test_rt07_valid_first_row_never_disappears():
    start_ms, _ = month_bounds_ms("2021-05")
    text = _row_line(start_ms) + "\n" + _row_line(start_ms + BAR_MS) + "\n"
    rows, meta = parse_kline_csv(text)
    assert len(rows) == 2
    assert rows[0].open_time_ms == start_ms


# ---------------------------------------------------------------------------
# RT-09: exact 12-column requirement + minute-alignment invariant
# ---------------------------------------------------------------------------
def test_rt09_11_columns_is_malformed():
    rows, meta = parse_kline_csv("1,2,3,4,5,6,7,8,9,10,11\n")
    assert rows == []
    assert meta["malformed_row_count"] == 1


def test_rt09_13_columns_is_malformed_not_silently_truncated():
    start_ms, _ = month_bounds_ms("2021-05")
    line = _row_line(start_ms) + ",unexpected_13th_column"
    rows, meta = parse_kline_csv(line + "\n")
    assert rows == []
    assert meta["malformed_row_count"] == 1


def test_rt09_trailing_comma_produces_a_13th_empty_column_and_is_malformed():
    start_ms, _ = month_bounds_ms("2021-05")
    line = _row_line(start_ms) + ","
    rows, meta = parse_kline_csv(line + "\n")
    assert rows == []
    assert meta["malformed_row_count"] == 1


def test_rt09_unaligned_minute_timestamp_is_an_invariant_violation():
    start_ms, _ = month_bounds_ms("2021-05")
    row = _kline_row(start_ms + 30_000)  # not divisible by 60_000
    violations = row_invariant_violations(row)
    assert "open_time_not_minute_aligned" in violations


def test_rt09_negative_zero_price_remains_a_valid_finite_zero():
    # explicit non-requirement: "-0" is numerically zero, still finite, and
    # still fails the pre-existing open>0 rule the same as ordinary zero --
    # no special-case rejection is required or added.
    start_ms, _ = month_bounds_ms("2021-05")
    row = _kline_row(start_ms, open=Decimal("-0"))
    violations = row_invariant_violations(row)
    assert "open_not_positive" in violations
    assert "open_not_finite" not in violations


# ---------------------------------------------------------------------------
# RT-10: CLI exit codes
# ---------------------------------------------------------------------------
def test_rt10_inventory_mode_always_exits_zero():
    rc = probe_cli.main(["--mode", "inventory"])
    assert rc == 0


def test_rt10_probe_mode_exits_nonzero_on_source_probe_failed(tmp_path: Path, monkeypatch):
    def _fake_run_probe(output_dir, months, timeout_seconds, git_commit_sha="UNKNOWN"):
        return probe_cli._build_report(
            "probe",
            [{**probe_cli._empty_month_record("2020-01"), "attempted": True, "month_passed": False}],
            git_commit_sha)

    monkeypatch.setattr(probe_cli, "run_probe", _fake_run_probe)
    rc = probe_cli.main(["--mode", "probe", "--output-dir", str(tmp_path), "--months", "2020-01"])
    assert rc == 1


def test_rt10_audit_local_exits_nonzero_when_local_audit_failed(tmp_path: Path):
    rc = probe_cli.main(["--mode", "audit-local", "--output-dir", str(tmp_path), "--months", "2021-05"])
    assert rc == 1  # no local file present -> LOCAL_AUDIT_FAILED


def test_rt10_audit_local_exits_zero_when_local_audit_passed(tmp_path: Path):
    year_month = "2021-02"
    csv_text = _full_month_csv(year_month)
    zip_bytes = _make_zip_bytes(year_month, csv_text)
    (tmp_path / local_zip_filename(year_month)).write_bytes(zip_bytes)
    digest = sha256_of_bytes(zip_bytes)
    (tmp_path / local_checksum_filename(year_month)).write_text(
        _checksum_text(digest, local_zip_filename(year_month)), encoding="utf-8")
    rc = probe_cli.main(["--mode", "audit-local", "--output-dir", str(tmp_path), "--months", year_month])
    assert rc == 0


# ---------------------------------------------------------------------------
# RT-08: atomic writes never leave a partially written canonical file
# ---------------------------------------------------------------------------
def test_rt08_atomic_write_leaves_no_temp_file_behind(tmp_path: Path):
    target = tmp_path / "some.file"
    probe_cli._atomic_write_bytes(target, b"hello")
    assert target.read_bytes() == b"hello"
    leftovers = [p for p in tmp_path.iterdir() if p != target]
    assert leftovers == []


def test_rt08_write_if_absent_never_touches_an_existing_file(tmp_path: Path):
    target = tmp_path / "some.checksum"
    target.write_text("original", encoding="utf-8")
    probe_cli._write_if_absent_atomic(target, "attempted replacement")
    assert target.read_text(encoding="utf-8") == "original"
