"""Network-free tests for the CORE_BTC_BINANCE_V0 materializer.

Fixtures are local synthetic ZIP+CHECKSUM pairs. No Binance HTTP.
"""
from __future__ import annotations

import inspect
import io
import json
import os
import resource
import subprocess
import sys
import time
import zipfile
from decimal import Decimal
from pathlib import Path

import pytest

import scripts.research.core_btc_binance_v0_materializer as mat_cli
from scripts.research.core_btc_binance_v0_materializer_lib import (
    BAR_MS,
    CANONICALIZATION_VERSION,
    CANONICAL_SCHEMA_VERSION,
    DECIMAL_STRING_POLICY,
    MATERIALIZER_VERSION,
    PYARROW_REQUIRED_MESSAGE,
    REPO_MANIFEST_PATH,
    SourceObject,
    acquire_all_verified,
    acquire_one_object,
    aggregate_htf,
    aggregate_htf_streaming,
    assert_disk_budget,
    atomic_write_bytes,
    audit_raw_object,
    bars_available_at_1m,
    bars_available_at_htf,
    build_frozen_source_plan,
    build_snapshot_identity,
    canonical_1m_path,
    canonical_1m_provenance_path,
    canonical_content_sha256_from_bars,
    canonical_content_sha256_from_parquet,
    canonical_rows_from_parquet,
    continuity_audit,
    continuity_audit_from_times,
    dataset_lock,
    dumps_deterministic,
    estimate_object_bytes,
    expected_global_minute_count,
    frozen_range_ms,
    gap_extreme_diagnostic,
    kline_to_canonical,
    load_all_canonical_1m,
    materialize_object_1m,
    merge_cross_object,
    part_files_size,
    parse_admit_current_raw,
    plan_report,
    remaining_extracted_csvs,
    require_pyarrow,
    raw_checksum_path,
    raw_zip_path,
    CoreBtcBinanceV0MaterializerError,
    StagePreconditionError,
    StaleCanonicalPartition,
    verify_canonical_partitions,
)
from scripts.research.core_btc_binance_v0_probe_lib import (
    KlineRow,
    day_bounds_ms,
    month_bounds_ms,
    sha256_of_bytes,
    sha256_of_file,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


def _row_line(open_time_ms, **kwargs):
    close_time_ms = kwargs.pop("close_time_ms", open_time_ms + BAR_MS - 1)
    vals = dict(
        open_="50000", high="50100", low="49900", close="50050",
        volume="12.5", quote_volume="625000", count="1000",
        taker_buy_base="6.25", taker_buy_quote="312500", ignore="0",
    )
    vals.update(kwargs)
    return ",".join(str(x) for x in (
        open_time_ms, vals["open_"], vals["high"], vals["low"], vals["close"],
        vals["volume"], close_time_ms, vals["quote_volume"], vals["count"],
        vals["taker_buy_base"], vals["taker_buy_quote"], vals["ignore"],
    ))


def _make_zip_bytes(member_name: str, csv_text: str) -> bytes:
    """ZIP bytes must be timestamp-stable so two clean directories hash equal."""
    buf = io.BytesIO()
    info = zipfile.ZipInfo(filename=member_name, date_time=(2020, 1, 1, 0, 0, 0))
    info.compress_type = zipfile.ZIP_STORED
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_STORED) as zf:
        zf.writestr(info, csv_text)
    return buf.getvalue()


def _checksum_text(digest: str, filename: str) -> str:
    return f"{digest}  {filename}\n"


def _monthly_obj(year_month: str) -> SourceObject:
    for obj in build_frozen_source_plan():
        if obj.source_period == year_month:
            return obj
    raise AssertionError(year_month)


def _daily_obj(ymd: str) -> SourceObject:
    for obj in build_frozen_source_plan():
        if obj.source_period == ymd:
            return obj
    raise AssertionError(ymd)


def _place_verified(root: Path, obj: SourceObject, csv_text: str, *, filename: str | None = None):
    zip_bytes = _make_zip_bytes(obj.expected_csv_member_name, csv_text)
    digest = sha256_of_bytes(zip_bytes)
    raw_zip_path(root, obj).parent.mkdir(parents=True, exist_ok=True)
    atomic_write_bytes(raw_zip_path(root, obj), zip_bytes)
    name = filename if filename is not None else obj.expected_zip_filename
    atomic_write_bytes(raw_checksum_path(root, obj), _checksum_text(digest, name).encode())
    return digest


def _place_all_one_row(root: Path) -> list[SourceObject]:
    objects = build_frozen_source_plan()
    for obj in objects:
        _place_verified(root, obj, _row_line(obj.period_start_ms) + "\n")
    return objects


def _materialize_all(root: Path, objects: list[SourceObject]) -> None:
    for obj in objects:
        rec = audit_raw_object(root, obj)
        out = materialize_object_1m(root, obj, rec)
        assert out["status"] in ("WROTE", "REUSED_IDENTICAL_PARTITION")


def _kline(open_time_ms: int) -> KlineRow:
    return KlineRow(
        open_time_ms, Decimal("100"), Decimal("110"), Decimal("90"), Decimal("105"),
        Decimal("1"), open_time_ms + BAR_MS - 1, Decimal("10"), 4,
        Decimal("0.4"), Decimal("4"),
    )


def test_frozen_source_plan_monthly_then_daily_exact_counts_and_order():
    objects = build_frozen_source_plan()
    monthly = [o for o in objects if o.archive_class == "monthly"]
    daily = [o for o in objects if o.archive_class == "daily"]
    assert len(monthly) == 79 and monthly[0].source_period == "2020-01"
    assert monthly[-1].source_period == "2026-07"
    assert len(daily) == 25 and daily[0].source_period == "2026-08-01"
    assert daily[-1].source_period == "2026-08-25"
    assert len(objects) == 104
    start, end = frozen_range_ms()
    assert start == 1577836800000 and end == 1787702400000
    assert expected_global_minute_count() == (end - start) // BAR_MS
    report = plan_report(objects, git_commit_sha="TEST")
    serialized = dumps_deterministic(report)
    assert serialized == dumps_deterministic(json.loads(serialized))


def test_cli_plan_writes_report_and_does_not_touch_repo_manifest(tmp_path: Path):
    repo_manifest = REPO_ROOT / REPO_MANIFEST_PATH
    before = repo_manifest.read_bytes()
    root = tmp_path / "ds"
    code = mat_cli.main(["--stage", "plan", "--dataset-root", str(root),
                         "--provenance-git-commit-sha", "TESTSHA"])
    assert code == 0
    plan = json.loads((root / "reports" / "source_plan.json").read_text())
    assert plan["source_object_count"] == 104
    assert repo_manifest.read_bytes() == before


def test_cli_acquire_refuses_without_allow_flag(tmp_path: Path):
    assert mat_cli.main(["--stage", "acquire", "--dataset-root", str(tmp_path)]) == 2


def test_portable_repo_path_constant_unpromoted():
    text = (REPO_ROOT / REPO_MANIFEST_PATH).read_text()
    assert "status: PLANNED_NOT_MATERIALIZED" in text
    assert "research_authorized: false" in text
    assert (REPO_ROOT / "docs").is_dir()


def test_verified_object_is_admitted(tmp_path: Path):
    obj = _daily_obj("2026-08-01")
    start, _ = day_bounds_ms("2026-08-01")
    digest = _place_verified(tmp_path, obj, _row_line(start) + "\n")
    rec = audit_raw_object(tmp_path, obj)
    assert rec["checksum_verification"] == "VERIFIED"
    assert rec["local_sha256"] == digest
    assert rec["admitted_to_canonical"] is True


def test_checksum_mismatch_rejected(tmp_path: Path):
    obj = _daily_obj("2026-08-01")
    start, _ = day_bounds_ms("2026-08-01")
    _place_verified(tmp_path, obj, _row_line(start) + "\n")
    raw_checksum_path(tmp_path, obj).write_text(
        _checksum_text("0" * 64, obj.expected_zip_filename))
    rec = audit_raw_object(tmp_path, obj)
    assert rec["checksum_verification"] == "MISMATCH"
    assert rec["admitted_to_canonical"] is False


def test_checksum_filename_identity_mismatch_rejected(tmp_path: Path):
    obj = _daily_obj("2026-08-01")
    start, _ = day_bounds_ms("2026-08-01")
    _place_verified(tmp_path, obj, _row_line(start) + "\n", filename="ETHUSDT-1m-2026-08-01.zip")
    rec = audit_raw_object(tmp_path, obj)
    assert rec["checksum_verification"] == "FILENAME_IDENTITY_MISMATCH"


def test_revision_conflict_preserves_old_zip_and_sidecar(tmp_path: Path):
    obj = _daily_obj("2026-08-01")
    zip_path = raw_zip_path(tmp_path, obj)
    side = raw_checksum_path(tmp_path, obj)
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    old = b"old-revision-bytes"
    zip_path.write_bytes(old)
    old_digest = sha256_of_bytes(old)
    side.write_text(_checksum_text(old_digest, obj.expected_zip_filename))
    new_digest = sha256_of_bytes(b"new-revision-bytes")

    def fetch(url: str):
        if url.endswith(".CHECKSUM"):
            return _checksum_text(new_digest, obj.expected_zip_filename).encode(), "HTTP_200", 80
        raise AssertionError("must not fetch zip on conflict")

    rec = acquire_one_object(tmp_path, obj, fetch, "T")
    assert rec["source_status"] == "REVISION_CONFLICT"
    assert zip_path.read_bytes() == old
    assert old_digest in side.read_text()


def test_sidecar_exists_zip_missing_remote_changed_is_conflict(tmp_path: Path):
    obj = _daily_obj("2026-08-01")
    side = raw_checksum_path(tmp_path, obj)
    side.parent.mkdir(parents=True)
    side.write_text(_checksum_text("cd" * 32, obj.expected_zip_filename))
    zip_bytes = _make_zip_bytes(obj.expected_csv_member_name, _row_line(day_bounds_ms("2026-08-01")[0]) + "\n")

    def fetch(url: str):
        if url.endswith(".CHECKSUM"):
            return _checksum_text(sha256_of_bytes(zip_bytes), obj.expected_zip_filename).encode(), "HTTP_200", 80
        return zip_bytes, "HTTP_200", len(zip_bytes)

    rec = acquire_one_object(tmp_path, obj, fetch, "T")
    assert rec["source_status"] == "REVISION_CONFLICT"
    assert rec["checksum_verification"] != "VERIFIED"
    assert not raw_zip_path(tmp_path, obj).exists()
    assert side.exists()


def test_http200_html_is_not_written_when_checksum_mismatches(tmp_path: Path):
    obj = _daily_obj("2026-08-01")
    html = b"<!DOCTYPE html><html>error</html>"

    def fetch(url: str):
        if url.endswith(".CHECKSUM"):
            return _checksum_text("ab" * 32, obj.expected_zip_filename).encode(), "HTTP_200", 80
        return html, "HTTP_200", len(html)

    rec = acquire_one_object(tmp_path, obj, fetch, "T")
    assert rec["checksum_verification"] == "MISMATCH"
    assert not raw_zip_path(tmp_path, obj).exists()


def test_part_file_is_discarded_and_never_audited_as_evidence(tmp_path: Path):
    obj = _daily_obj("2026-08-01")
    part = raw_zip_path(tmp_path, obj).with_suffix(".zip.part")
    part.parent.mkdir(parents=True, exist_ok=True)
    part.write_bytes(b"truncated")
    start, _ = day_bounds_ms("2026-08-01")
    zip_bytes = _make_zip_bytes(obj.expected_csv_member_name, _row_line(start) + "\n")
    digest = sha256_of_bytes(zip_bytes)

    def fetch(url: str):
        if url.endswith(".CHECKSUM"):
            return _checksum_text(digest, obj.expected_zip_filename).encode(), "HTTP_200", 80
        return zip_bytes, "HTTP_200", len(zip_bytes)

    rec = acquire_one_object(tmp_path, obj, fetch, "T")
    assert rec["checksum_verification"] == "VERIFIED"
    assert not part.exists()


def test_restart_reuses_verified_raw_file(tmp_path: Path):
    obj = _daily_obj("2026-08-01")
    start, _ = day_bounds_ms("2026-08-01")
    digest = _place_verified(tmp_path, obj, _row_line(start) + "\n")

    def fetch(url: str):
        if url.endswith(".CHECKSUM"):
            return _checksum_text(digest, obj.expected_zip_filename).encode(), "HTTP_200", 80
        raise AssertionError("must not re-download verified zip")

    rec = acquire_one_object(tmp_path, obj, fetch, "T")
    assert rec["disposition"] == "REUSED_IDENTICAL"
    assert rec["checksum_verification"] == "VERIFIED"


def test_exact_monthly_and_daily_member_identity(tmp_path: Path):
    monthly = _monthly_obj("2026-07")
    assert monthly.expected_csv_member_name == "BTCUSDT-1m-2026-07.csv"
    start, _ = month_bounds_ms("2026-07")
    zip_bytes = _make_zip_bytes("BTCUSDT-1m-2026-07-01.csv", _row_line(start) + "\n")
    atomic_write_bytes(raw_zip_path(tmp_path, monthly), zip_bytes)
    atomic_write_bytes(
        raw_checksum_path(tmp_path, monthly),
        _checksum_text(sha256_of_bytes(zip_bytes), monthly.expected_zip_filename).encode())
    rec = audit_raw_object(tmp_path, monthly)
    assert rec["parser_status"] == "MISSING_EXPECTED_CSV_MEMBER"


def test_malformed_and_nan_inf_rejected(tmp_path: Path):
    obj = _daily_obj("2026-08-01")
    start, _ = day_bounds_ms("2026-08-01")
    csv = "\n".join([
        _row_line(start),
        _row_line(start + BAR_MS, open_="NaN"),
        _row_line(start + 2 * BAR_MS, volume="Infinity"),
        "1,2,3",
    ]) + "\n"
    _place_verified(tmp_path, obj, csv)
    rec = audit_raw_object(tmp_path, obj)
    assert rec["malformed_row_count"] == 3
    mat = materialize_object_1m(tmp_path, obj, rec)
    assert mat["admitted_rows"] == 1


def test_minute_alignment_rejected(tmp_path: Path):
    obj = _daily_obj("2026-08-01")
    start, _ = day_bounds_ms("2026-08-01")
    _place_verified(tmp_path, obj, _row_line(start + 1) + "\n")
    rec = audit_raw_object(tmp_path, obj)
    mat = materialize_object_1m(tmp_path, obj, rec)
    assert mat["admitted_rows"] == 0
    assert mat["rejected_invariant"] == 1


def test_monthly_to_daily_boundary_is_continuous(tmp_path: Path):
    monthly = _monthly_obj("2026-07")
    daily = _daily_obj("2026-08-01")
    _july_start, july_end = month_bounds_ms("2026-07")
    last_july = july_end - BAR_MS
    first_aug, _ = day_bounds_ms("2026-08-01")
    assert first_aug == last_july + BAR_MS
    _place_verified(tmp_path, monthly, _row_line(last_july) + "\n")
    _place_verified(tmp_path, daily, _row_line(first_aug) + "\n")
    for obj in (monthly, daily):
        rec = audit_raw_object(tmp_path, obj)
        materialize_object_1m(tmp_path, obj, rec)
    bars = load_all_canonical_1m(tmp_path, [monthly, daily])
    assert [b.open_time_ms for b in bars] == [last_july, first_aug]
    assert bars[0].available_at_ms == first_aug


def test_end_exclusive_2026_08_26_never_enters_dataset(tmp_path: Path):
    obj = _daily_obj("2026-08-25")
    _start, end = day_bounds_ms("2026-08-25")
    last_ok = end - BAR_MS
    forbidden = frozen_range_ms()[1]
    _place_verified(tmp_path, obj, _row_line(last_ok) + "\n" + _row_line(forbidden) + "\n")
    rec = audit_raw_object(tmp_path, obj)
    mat = materialize_object_1m(tmp_path, obj, rec)
    bars = canonical_rows_from_parquet(canonical_1m_path(tmp_path, obj))
    assert all(b.open_time_ms < forbidden for b in bars)
    assert mat["rejected_identity"] + mat["rejected_end_exclusive"] >= 1


def test_close_time_ms_round_trip_does_not_change_available_at(tmp_path: Path):
    obj = _daily_obj("2026-08-01")
    start, _ = day_bounds_ms("2026-08-01")
    _place_verified(tmp_path, obj, _row_line(start) + "\n")
    rec = audit_raw_object(tmp_path, obj)
    materialize_object_1m(tmp_path, obj, rec)
    bar = canonical_rows_from_parquet(canonical_1m_path(tmp_path, obj))[0]
    assert bar.close_time_ms == start + BAR_MS - 1
    assert bar.available_at_ms == start + BAR_MS
    assert bar.available_at_ms != bar.close_time_ms
    import pyarrow.parquet as pq
    names = pq.read_schema(canonical_1m_path(tmp_path, obj)).names
    assert "close_time_ms" in names
    assert "source_sha256" not in names


def test_identical_vs_conflicting_duplicates(tmp_path: Path):
    obj = _daily_obj("2026-08-01")
    start, _ = day_bounds_ms("2026-08-01")
    csv = "\n".join([
        _row_line(start), _row_line(start),
        _row_line(start + BAR_MS, close="50051"),
        _row_line(start + BAR_MS, close="50052"),
    ]) + "\n"
    _place_verified(tmp_path, obj, csv)
    rec = audit_raw_object(tmp_path, obj)
    mat = materialize_object_1m(tmp_path, obj, rec)
    assert mat["identical_duplicate_count"] == 1
    assert mat["conflicting_duplicate_open_times"] == [start + BAR_MS]


def test_cross_object_overlap_conflict(tmp_path: Path):
    a = _daily_obj("2026-08-01")
    b = _daily_obj("2026-08-02")
    t, _ = day_bounds_ms("2026-08-01")
    _place_verified(tmp_path, a, _row_line(t, close="50050") + "\n")
    zip_bytes = _make_zip_bytes(b.expected_csv_member_name, _row_line(t, close="50099") + "\n")
    atomic_write_bytes(raw_zip_path(tmp_path, b), zip_bytes)
    atomic_write_bytes(
        raw_checksum_path(tmp_path, b),
        _checksum_text(sha256_of_bytes(zip_bytes), b.expected_zip_filename).encode())
    ra, rb = audit_raw_object(tmp_path, a), audit_raw_object(tmp_path, b)
    materialize_object_1m(tmp_path, a, ra)
    mb = materialize_object_1m(tmp_path, b, rb)
    assert mb["rejected_identity"] == 1
    from scripts.research.core_btc_binance_v0_materializer_lib import CanonicalBar, canonical_rows_to_parquet_bytes
    foreign = CanonicalBar(**{**kline_to_canonical(_kline(t), b).__dict__, "close": Decimal("50099")})
    atomic_write_bytes(canonical_1m_path(tmp_path, b), canonical_rows_to_parquet_bytes([foreign]))
    merged, stats = merge_cross_object(load_all_canonical_1m(tmp_path, [a, b]))
    assert stats["cross_object_conflicting_duplicate_count"] == 1
    assert merged == []


def test_one_missing_minute_and_contiguous_gap_and_by_month():
    start = 1577836800000
    bars = [kline_to_canonical(_kline(start + i * BAR_MS), _monthly_obj("2020-01"))
            for i in (0, 1, 4, 5)]
    audit = continuity_audit(bars, start_ms=start, end_ms=start + 6 * BAR_MS)
    assert audit["missing_minute_count"] == 2
    assert audit["gaps"][0]["start_ms"] == start + 2 * BAR_MS
    assert audit["gaps"][0]["end_exclusive_ms"] == start + 4 * BAR_MS
    assert audit["missingness_by_month"]["2020-01"] == 2


def test_streaming_gap_audit_full_range_empty_is_one_gap():
    start, end = frozen_range_ms()
    audit = continuity_audit_from_times([], start_ms=start, end_ms=end)
    assert audit["missing_minute_count"] == expected_global_minute_count()
    assert len(audit["gaps"]) == 1
    assert audit["gaps"][0]["start_ms"] == start
    assert audit["gaps"][0]["end_exclusive_ms"] == end


def test_no_synthetic_gap_repair_in_materialize(tmp_path: Path):
    obj = _daily_obj("2026-08-01")
    start, _ = day_bounds_ms("2026-08-01")
    _place_verified(tmp_path, obj, _row_line(start) + "\n")
    rec = audit_raw_object(tmp_path, obj)
    materialize_object_1m(tmp_path, obj, rec)
    assert len(canonical_rows_from_parquet(canonical_1m_path(tmp_path, obj))) == 1


def test_canonical_order_and_repeated_materialization_deterministic(tmp_path: Path):
    obj = _daily_obj("2026-08-01")
    start, _ = day_bounds_ms("2026-08-01")
    _place_verified(tmp_path, obj, _row_line(start + BAR_MS) + "\n" + _row_line(start) + "\n")
    rec = audit_raw_object(tmp_path, obj)
    materialize_object_1m(tmp_path, obj, rec)
    path = canonical_1m_path(tmp_path, obj)
    first = sha256_of_file(path)
    assert [b.open_time_ms for b in canonical_rows_from_parquet(path)] == [start, start + BAR_MS]
    out = materialize_object_1m(tmp_path, obj, audit_raw_object(tmp_path, obj))
    assert out["status"] == "REUSED_IDENTICAL_PARTITION"
    assert sha256_of_file(path) == first
    assert canonical_1m_provenance_path(tmp_path, obj).exists()


def test_parquet_decimal_round_trip(tmp_path: Path):
    obj = _daily_obj("2026-08-01")
    start, _ = day_bounds_ms("2026-08-01")
    _place_verified(tmp_path, obj, _row_line(
        start, open_="7189.43", high="7190.52", low="7177", close="7182.44", volume="246.092") + "\n")
    rec = audit_raw_object(tmp_path, obj)
    materialize_object_1m(tmp_path, obj, rec)
    bar = canonical_rows_from_parquet(canonical_1m_path(tmp_path, obj))[0]
    assert bar.open == Decimal("7189.43")
    assert "format(Decimal" in DECIMAL_STRING_POLICY


def test_rt_m01_stale_audit_changed_zip_fails_closed(tmp_path: Path):
    obj = _daily_obj("2026-08-01")
    start, _ = day_bounds_ms("2026-08-01")
    _place_verified(tmp_path, obj, _row_line(start, close="50050") + "\n")
    rec_audit = audit_raw_object(tmp_path, obj)
    zip_b = _make_zip_bytes(obj.expected_csv_member_name, _row_line(start, close="50099") + "\n")
    raw_zip_path(tmp_path, obj).write_bytes(zip_b)
    mat = materialize_object_1m(tmp_path, obj, rec_audit)
    assert mat["status"] in ("STALE_AUDIT", "SKIPPED_NOT_VERIFIED")
    assert not canonical_1m_path(tmp_path, obj).exists()
    # Verified revision B on disk, but materialize is given audit A.
    _place_verified(tmp_path, obj, _row_line(start, close="50099") + "\n")
    mat2 = materialize_object_1m(tmp_path, obj, rec_audit)
    assert mat2["status"] == "STALE_AUDIT"
    assert not canonical_1m_path(tmp_path, obj).exists()


def _n_bars(n: int, start: int, obj: SourceObject) -> list:
    return [kline_to_canonical(_kline(start + i * BAR_MS), obj) for i in range(n)]


def test_htf_5m_15m_1h_4h_complete_and_incomplete():
    obj = _monthly_obj("2020-01")
    start, _ = month_bounds_ms("2020-01")
    complete_4h = _n_bars(240, start, obj)
    rows_5 = aggregate_htf(complete_4h, 5, start_ms=start, end_ms=start + 240 * BAR_MS)
    rows_4h = aggregate_htf(complete_4h, 240, start_ms=start, end_ms=start + 240 * BAR_MS)
    assert len(rows_5) == 48 and all(r.is_complete for r in rows_5)
    assert rows_4h[0].is_complete and rows_4h[0].available_at_ms == start + 240 * BAR_MS
    bad_5 = aggregate_htf(complete_4h[:-1], 5, start_ms=start, end_ms=start + 240 * BAR_MS)
    assert bad_5[-1].is_complete is False and bad_5[-1].open is None


def test_incomplete_htf_does_not_leak_partial_ohlc():
    obj = _monthly_obj("2020-01")
    start, _ = month_bounds_ms("2020-01")
    rows = aggregate_htf(_n_bars(4, start, obj), 5, start_ms=start, end_ms=start + 5 * BAR_MS)
    assert rows[0].is_complete is False and rows[0].open is None


def test_no_lookahead_1m_and_htf():
    obj = _monthly_obj("2020-01")
    start, _ = month_bounds_ms("2020-01")
    bars = _n_bars(5, start, obj)
    assert [b.open_time_ms for b in bars_available_at_1m(bars, start + BAR_MS)] == [start]
    assert bars[0].available_at_ms == start + BAR_MS
    assert bars[0].close_time_ms == start + BAR_MS - 1
    htf = aggregate_htf(bars, 5, start_ms=start, end_ms=start + 5 * BAR_MS)
    assert bars_available_at_htf(htf, start + 4 * BAR_MS) == []
    assert bars_available_at_htf(htf, start + 5 * BAR_MS)[0].is_complete


def test_streaming_htf_monthly_daily_partition_boundary(tmp_path: Path):
    objects = _place_all_one_row(tmp_path)
    july = _monthly_obj("2026-07")
    aug = _daily_obj("2026-08-01")
    last_july = july.period_end_exclusive_ms - BAR_MS
    first_aug = aug.period_start_ms
    _place_verified(tmp_path, july, _row_line(last_july) + "\n")
    _place_verified(tmp_path, aug, _row_line(first_aug) + "\n")
    _materialize_all(tmp_path, objects)
    summary = aggregate_htf_streaming(tmp_path, objects)
    assert summary["5m"]["expected_buckets"] == expected_global_minute_count() // 5
    import pyarrow.parquet as pq
    found = None
    pf = pq.ParquetFile(tmp_path / "canonical" / "5m" / "bars.parquet")
    for batch in pf.iter_batches(columns=["open_time_ms", "available_at_ms", "is_complete"]):
        times = batch.column("open_time_ms").to_pylist()
        avails = batch.column("available_at_ms").to_pylist()
        for t, a in zip(times, avails):
            if int(t) == first_aug:
                found = int(a)
                break
        if found is not None:
            break
    assert found == first_aug + 5 * BAR_MS


def test_snapshot_id_stable_and_changes_with_checksum_or_version():
    objects = build_frozen_source_plan()[:2]
    inventory = [
        {"source_period": o.source_period, "archive_class": o.archive_class,
         "source_url": o.source_url, "local_sha256": "aa" * 32,
         "expected_sha256": "aa" * 32, "checksum_verification": "VERIFIED",
         "byte_size": 10}
        for o in objects
    ]
    kwargs = dict(objects=objects, quality_report_sha256="q1",
                  output_checksums={"canonical/1m/x.parquet": "bb" * 32},
                  contract_sha256="cc" * 32, git_commit_sha="deadbeef")
    a = build_snapshot_identity(inventory=inventory, **kwargs)
    b = build_snapshot_identity(inventory=inventory, **kwargs)
    assert a["snapshot_id"] == b["snapshot_id"]
    inventory2 = [{**inventory[0], "local_sha256": "dd" * 32}, inventory[1]]
    c = build_snapshot_identity(inventory=inventory2, **kwargs)
    assert c["snapshot_id"] != a["snapshot_id"]
    from scripts.research.core_btc_binance_v0_materializer_lib import sha256_of_canonical_identity_payload
    payload_changed = dict(a["identity_payload"])
    payload_changed["materializer_version"] = MATERIALIZER_VERSION + 1
    assert sha256_of_canonical_identity_payload(payload_changed) != a["snapshot_id"]
    d = build_snapshot_identity(
        inventory=inventory, objects=objects, quality_report_sha256="q1",
        output_checksums={"canonical/1m/x.parquet": "ee" * 32},
        contract_sha256="cc" * 32, git_commit_sha="deadbeef")
    assert d["snapshot_id"] != a["snapshot_id"]


def test_atomic_output_adoption_and_no_permanent_csv(tmp_path: Path):
    obj = _daily_obj("2026-08-01")
    start, _ = day_bounds_ms("2026-08-01")
    _place_verified(tmp_path, obj, _row_line(start) + "\n")
    materialize_object_1m(tmp_path, obj, audit_raw_object(tmp_path, obj))
    assert remaining_extracted_csvs(tmp_path) == []


def test_disk_safety_gate(tmp_path: Path):
    assert assert_disk_budget(tmp_path, estimated_download_bytes=1, disk_reserve_bytes=1)["disk_safety_ok"]
    with pytest.raises(Exception):
        assert_disk_budget(tmp_path, estimated_download_bytes=10**18, disk_reserve_bytes=10**18)


def test_head_content_length_zero_and_missing_are_unknown():
    z0, origin0 = estimate_object_bytes("monthly", 0)
    z_none, origin_none = estimate_object_bytes("monthly", None)
    z_neg, _origin = estimate_object_bytes("daily", -5)
    assert z0 > 0 and origin0.startswith("CONSERVATIVE")
    assert z_none > 0 and origin_none.startswith("CONSERVATIVE")
    assert z_neg > 0
    z_ok, origin_ok = estimate_object_bytes("monthly", 1844583)
    assert z_ok == 1844583 and origin_ok == "HEAD_CONTENT_LENGTH"


def test_part_files_counted_in_disk_usage(tmp_path: Path):
    p = tmp_path / "raw" / "monthly" / "2020-01"
    p.mkdir(parents=True)
    (p / "BTCUSDT-1m-2020-01.zip.part").write_bytes(b"x" * 4096)
    assert part_files_size(tmp_path) == 4096


def test_reserve_zero_refused_without_unsafe_flag(tmp_path: Path):
    with pytest.raises(CoreBtcBinanceV0MaterializerError):
        assert_disk_budget(tmp_path, estimated_download_bytes=1, disk_reserve_bytes=0)
    assert assert_disk_budget(
        tmp_path, estimated_download_bytes=1, disk_reserve_bytes=0, allow_zero_reserve=True,
    )["disk_safety_ok"]
    assert mat_cli.main([
        "--stage", "plan", "--dataset-root", str(tmp_path), "--disk-reserve-bytes", "0",
    ]) == 2


def test_gap_extreme_diagnostic_is_deterministic_and_does_not_repair():
    obj = _monthly_obj("2020-01")
    start, _ = month_bounds_ms("2020-01")
    bars = _n_bars(3, start, obj)
    bars[0] = kline_to_canonical(
        KlineRow(start, Decimal("100"), Decimal("110"), Decimal("90"), Decimal("200"),
                 Decimal("999999"), start + BAR_MS - 1, Decimal("10"), 4,
                 Decimal("0.4"), Decimal("4")),
        obj)
    audit = continuity_audit(bars, start_ms=start, end_ms=start + 5 * BAR_MS)
    diag = gap_extreme_diagnostic(bars, audit["gaps"])
    assert "99th percentile" in diag["rule"]
    assert dumps_deterministic(diag) == dumps_deterministic(gap_extreme_diagnostic(bars, audit["gaps"]))
    assert audit["observed_unique_timestamps"] == 3


def test_utc_alignment_and_available_at_never_uses_close_time():
    obj = _monthly_obj("2020-01")
    start, _ = month_bounds_ms("2020-01")
    bar = kline_to_canonical(_kline(start), obj)
    assert bar.available_at_ms == start + BAR_MS
    assert bar.close_time_ms == start + BAR_MS - 1


def test_aggregate_before_canonical_fails(tmp_path: Path):
    assert mat_cli.main(["--stage", "aggregate", "--dataset-root", str(tmp_path),
                         "--provenance-git-commit-sha", "T"]) != 0


def test_finalize_before_canonical_fails(tmp_path: Path):
    assert mat_cli.main(["--stage", "finalize", "--dataset-root", str(tmp_path),
                         "--provenance-git-commit-sha", "T"]) != 0


def test_finalize_empty_root_fails(tmp_path: Path):
    root = tmp_path / "empty"
    assert mat_cli.main(["--stage", "finalize", "--dataset-root", str(root),
                         "--provenance-git-commit-sha", "T"]) != 0
    assert not (root / "manifests" / "CORE_BTC_BINANCE_V0.candidate.json").exists()


def test_audit_without_raw_fails(tmp_path: Path):
    assert mat_cli.main(["--stage", "audit-raw", "--dataset-root", str(tmp_path),
                         "--provenance-git-commit-sha", "T"]) != 0


def test_materialize_without_verified_raw_fails(tmp_path: Path):
    assert mat_cli.main(["--stage", "materialize-1m", "--dataset-root", str(tmp_path),
                         "--provenance-git-commit-sha", "T"]) != 0


def test_stage_all_without_allow_is_refused(tmp_path: Path):
    assert mat_cli.main(["--stage", "all", "--dataset-root", str(tmp_path)]) == 2


def test_acquire_one_checksum_failure_is_nonzero(tmp_path: Path, monkeypatch):
    def fetch(url: str):
        if url.endswith(".CHECKSUM"):
            return b"not-a-checksum", "HTTP_200", 10
        return b"zip", "HTTP_200", 3

    monkeypatch.setattr(mat_cli, "_sync_get_fetch", lambda _t: fetch)
    code = mat_cli.main([
        "--stage", "acquire", "--allow-acquire", "--dataset-root", str(tmp_path),
        "--provenance-git-commit-sha", "T",
    ])
    assert code != 0


def test_stage_all_one_failed_object_stops_before_finalize(tmp_path: Path, monkeypatch):
    def head(_url: str):
        return b"", "HTTP_200", 1024

    def get(url: str):
        if url.endswith(".CHECKSUM"):
            return b"not-a-checksum", "HTTP_200", 10
        return b"zip", "HTTP_200", 3

    monkeypatch.setattr(mat_cli, "_sync_head_fetch", lambda _t: head)
    monkeypatch.setattr(mat_cli, "_sync_get_fetch", lambda _t: get)
    code = mat_cli.main([
        "--stage", "all", "--allow-acquire", "--dataset-root", str(tmp_path),
        "--provenance-git-commit-sha", "T",
    ])
    assert code != 0
    assert not (tmp_path / "reports" / "snapshot_manifest.json").exists()
    assert not (tmp_path / "manifests" / "CORE_BTC_BINANCE_V0.candidate.json").exists()


def test_stage_all_zero_verified_is_nonzero(tmp_path: Path, monkeypatch):
    def head(_url: str):
        return b"", "HTTP_200", None

    def get(_url: str):
        return None, "HTTP_404", None

    monkeypatch.setattr(mat_cli, "_sync_head_fetch", lambda _t: head)
    monkeypatch.setattr(mat_cli, "_sync_get_fetch", lambda _t: get)
    code = mat_cli.main([
        "--stage", "all", "--allow-acquire", "--dataset-root", str(tmp_path),
        "--provenance-git-commit-sha", "T",
    ])
    assert code != 0
    assert not (tmp_path / "reports" / "snapshot_manifest.json").exists()


def test_rt_m02_stale_partition_finalize_fails(tmp_path: Path):
    objects = _place_all_one_row(tmp_path)
    _materialize_all(tmp_path, objects)
    obj = _daily_obj("2026-08-01")
    _place_verified(tmp_path, obj, _row_line(obj.period_start_ms, close="50022") + "\n")
    code = mat_cli.main(["--stage", "finalize", "--dataset-root", str(tmp_path),
                         "--provenance-git-commit-sha", "T"])
    assert code != 0
    assert not (tmp_path / "reports" / "snapshot_manifest.json").exists()
    with pytest.raises((StaleCanonicalPartition, StagePreconditionError)):
        verify_canonical_partitions(tmp_path, objects)


def test_quality_report_sha256_equals_file_bytes(tmp_path: Path):
    objects = _place_all_one_row(tmp_path)
    _materialize_all(tmp_path, objects)
    assert mat_cli.main(["--stage", "aggregate", "--dataset-root", str(tmp_path),
                         "--provenance-git-commit-sha", "T"]) == 0
    assert mat_cli.main(["--stage", "finalize", "--dataset-root", str(tmp_path),
                         "--provenance-git-commit-sha", "T"]) == 0
    qpath = tmp_path / "reports" / "quality_report.json"
    snap = json.loads((tmp_path / "reports" / "snapshot_manifest.json").read_text())
    assert sha256_of_file(qpath) == snap["identity_payload"]["quality_report_sha256"]
    quality = json.loads(qpath.read_text())
    assert "snapshot_id" not in quality
    assert "quality_report_sha256" not in quality
    cand = json.loads((tmp_path / "manifests" / "CORE_BTC_BINANCE_V0.candidate.json").read_text())
    assert cand["status"] == "MATERIALIZED_UNVERIFIED"
    assert cand["research_authorized"] is False
    assert "status: PLANNED_NOT_MATERIALIZED" in (REPO_ROOT / REPO_MANIFEST_PATH).read_text()


def test_snapshot_identical_in_two_clean_directories(tmp_path: Path):
    ids = []
    for name in ("a", "b"):
        root = tmp_path / name
        objects = _place_all_one_row(root)
        _materialize_all(root, objects)
        assert mat_cli.main(["--stage", "aggregate", "--dataset-root", str(root),
                             "--provenance-git-commit-sha", "SAME"]) == 0
        assert mat_cli.main(["--stage", "finalize", "--dataset-root", str(root),
                             "--provenance-git-commit-sha", "SAME"]) == 0
        snap = json.loads((root / "reports" / "snapshot_manifest.json").read_text())
        ids.append(snap["snapshot_id"])
        assert sha256_of_file(root / "reports" / "quality_report.json") == (
            snap["identity_payload"]["quality_report_sha256"])
    assert ids[0] == ids[1]


def test_mutation_lock_rejects_concurrent_writer(tmp_path: Path):
    root = tmp_path / "ds"
    holder = subprocess.Popen(
        [sys.executable, "-c",
         "import time\nfrom pathlib import Path\n"
         "from scripts.research.core_btc_binance_v0_materializer_lib import dataset_lock\n"
         f"p=Path({str(root)!r})\n"
         "p.mkdir(parents=True, exist_ok=True)\n"
         "with dataset_lock(p):\n"
         "    time.sleep(12)\n"],
        cwd=str(REPO_ROOT),
        env={**os.environ, "PYTHONPATH": str(REPO_ROOT)},
    )
    try:
        time.sleep(0.5)
        with pytest.raises(CoreBtcBinanceV0MaterializerError):
            with dataset_lock(root):
                pass
    finally:
        holder.kill()
        holder.wait(timeout=5)


def test_require_pyarrow_message_names_research_requirements():
    assert "requirements-research.txt" in PYARROW_REQUIRED_MESSAGE
    assert "pyarrow==17.0.0" in PYARROW_REQUIRED_MESSAGE


def test_missing_pyarrow_startup(monkeypatch):
    class _BlockPyarrow:
        def find_spec(self, name, path=None, target=None):
            if name == "pyarrow" or (name and name.startswith("pyarrow.")):
                raise ImportError("blocked")
            return None

    for k in list(sys.modules):
        if k == "pyarrow" or k.startswith("pyarrow."):
            monkeypatch.delitem(sys.modules, k, raising=False)
    finder = _BlockPyarrow()
    sys.meta_path.insert(0, finder)
    try:
        with pytest.raises(CoreBtcBinanceV0MaterializerError) as ei:
            require_pyarrow()
        assert "requirements-research.txt" in str(ei.value)
    finally:
        sys.meta_path.remove(finder)
        import pyarrow  # noqa: F401
        import pyarrow.parquet  # noqa: F401


def test_streaming_reader_uses_iter_batches_not_full_table(tmp_path: Path, monkeypatch):
    import pyarrow.parquet as pq
    import scripts.research.core_btc_binance_v0_materializer_lib as lib

    src_iter = inspect.getsource(lib.iter_canonical_batches)
    src_agg = inspect.getsource(lib.aggregate_htf_streaming)
    src_cont = inspect.getsource(lib.continuity_audit_from_root)
    assert "iter_batches" in src_iter
    assert "read_table" not in src_iter
    assert "iter_canonical_batches" in src_agg
    assert "load_all_canonical_1m" not in src_agg
    assert "iter_canonical_open_times" in src_cont

    def boom(*_a, **_k):
        raise AssertionError("load_all_canonical_1m must not run during streaming aggregate")

    monkeypatch.setattr(lib, "load_all_canonical_1m", boom)
    real_read = pq.read_table

    def guarded_read(*args, **kwargs):
        table = real_read(*args, **kwargs)
        if table.num_rows > 50_000:
            raise AssertionError("pq.read_table loaded a large concatenated table")
        return table

    monkeypatch.setattr(pq, "read_table", guarded_read)
    objects = _place_all_one_row(tmp_path)
    _materialize_all(tmp_path, objects)
    summary = lib.aggregate_htf_streaming(tmp_path, objects)
    assert summary["5m"]["complete_buckets"] + summary["5m"]["incomplete_buckets"] == (
        expected_global_minute_count() // 5)


def test_memory_and_scalability_many_partition_rows(tmp_path: Path):
    """Subprocess-isolated peak RSS: many partitions, no full CanonicalBar list."""
    script = r"""
import json, os, resource, sys
from pathlib import Path
sys.path.insert(0, os.environ["REPO_ROOT"])
from tests.research.test_core_btc_binance_v0_materializer import (
    _place_verified, _row_line, _monthly_obj, _materialize_all,
)
from scripts.research.core_btc_binance_v0_materializer_lib import build_frozen_source_plan
import scripts.research.core_btc_binance_v0_materializer as mat_cli
from scripts.research.core_btc_binance_v0_probe_lib import sha256_of_file

root = Path(os.environ["DATASET_ROOT"])
objects = build_frozen_source_plan()
dense = {_monthly_obj("2020-01").source_period,
         _monthly_obj("2020-02").source_period,
         _monthly_obj("2020-03").source_period}
n = 35_000
for obj in objects:
    if obj.source_period in dense:
        start = obj.period_start_ms
        csv = "\n".join(_row_line(start + i * 60_000) for i in range(n)) + "\n"
        _place_verified(root, obj, csv)
    else:
        _place_verified(root, obj, _row_line(obj.period_start_ms) + "\n")
_materialize_all(root, objects)
assert mat_cli.main(["--stage", "aggregate", "--dataset-root", str(root),
                     "--provenance-git-commit-sha", "T"]) == 0
assert mat_cli.main(["--stage", "finalize", "--dataset-root", str(root),
                     "--provenance-git-commit-sha", "T"]) == 0
peak_mb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0
snap = json.loads((root / "reports" / "snapshot_manifest.json").read_text())
assert sha256_of_file(root / "reports" / "quality_report.json") == (
    snap["identity_payload"]["quality_report_sha256"])
print(f"PEAK_RSS_MIB={peak_mb:.1f}")
raise SystemExit(0 if peak_mb < 1000 else 3)
"""
    env = {**os.environ, "REPO_ROOT": str(REPO_ROOT), "DATASET_ROOT": str(tmp_path),
           "PYTHONPATH": str(REPO_ROOT)}
    proc = subprocess.run(
        [sys.executable, "-c", script], cwd=str(REPO_ROOT), env=env,
        capture_output=True, text=True, timeout=180,
    )
    assert proc.returncode == 0, proc.stderr + proc.stdout
    assert "PEAK_RSS_MIB=" in proc.stdout
    peak = float(proc.stdout.strip().split("PEAK_RSS_MIB=")[-1].split()[0])
    print(f"isolated_peak_rss_mib={peak:.1f}")
    assert peak < 1000, f"peak RSS {peak:.1f} MiB exceeds 1 GiB"


def test_rt_m12_revision_conflict_with_verified_local_pair_fails_acquire(tmp_path: Path, monkeypatch):
    objects = _place_all_one_row(tmp_path)
    obj0 = objects[0]
    old_zip = raw_zip_path(tmp_path, obj0).read_bytes()
    old_side = raw_checksum_path(tmp_path, obj0).read_bytes()

    def fetch(url: str):
        name = url.rsplit("/", 1)[-1]
        if url.endswith(".CHECKSUM"):
            zip_name = name[:-len(".CHECKSUM")] if name.endswith(".CHECKSUM") else name
            return f"{'cd' * 32}  {zip_name}\n".encode(), "HTTP_200", 80
        raise AssertionError("must not GET zip on revision conflict")

    monkeypatch.setattr(mat_cli, "_sync_get_fetch", lambda _t: fetch)
    code = mat_cli.main([
        "--stage", "acquire", "--allow-acquire", "--dataset-root", str(tmp_path),
        "--provenance-git-commit-sha", "T",
    ])
    assert code != 0
    assert raw_zip_path(tmp_path, obj0).read_bytes() == old_zip
    assert raw_checksum_path(tmp_path, obj0).read_bytes() == old_side
    fake = [{"checksum_verification": "VERIFIED", "disposition": "REVISION_CONFLICT",
             "source_status": "REVISION_CONFLICT"}] * 104
    assert acquire_all_verified(fake, 104) is False


def test_rt_m12_stage_all_conflict_stops_without_snapshot(tmp_path: Path, monkeypatch):
    _place_all_one_row(tmp_path)

    def head(_url: str):
        return b"", "HTTP_200", 1024

    def get(url: str):
        name = url.rsplit("/", 1)[-1]
        if url.endswith(".CHECKSUM"):
            zip_name = name[:-len(".CHECKSUM")] if name.endswith(".CHECKSUM") else name
            return f"{'cd' * 32}  {zip_name}\n".encode(), "HTTP_200", 80
        raise AssertionError("must not GET zip on revision conflict")

    monkeypatch.setattr(mat_cli, "_sync_head_fetch", lambda _t: head)
    monkeypatch.setattr(mat_cli, "_sync_get_fetch", lambda _t: get)
    code = mat_cli.main([
        "--stage", "all", "--allow-acquire", "--dataset-root", str(tmp_path),
        "--provenance-git-commit-sha", "T",
    ])
    assert code != 0
    assert not (tmp_path / "reports" / "snapshot_manifest.json").exists()
    assert not (tmp_path / "manifests" / "CORE_BTC_BINANCE_V0.candidate.json").exists()


def test_canonical_content_digest_deterministic_and_sensitive(tmp_path: Path):
    obj = _daily_obj("2026-08-01")
    start, _ = day_bounds_ms("2026-08-01")
    a = [kline_to_canonical(_kline(start + i * BAR_MS), obj) for i in range(8)]
    b = [kline_to_canonical(_kline(start + i * BAR_MS), obj) for i in range(8)]
    da = canonical_content_sha256_from_bars(a)
    db = canonical_content_sha256_from_bars(b)
    assert da["canonical_content_sha256"] == db["canonical_content_sha256"]
    a_price = list(a)
    a_price[0] = kline_to_canonical(
        KlineRow(start, Decimal("101"), Decimal("110"), Decimal("90"), Decimal("105"),
                 Decimal("1"), start + BAR_MS - 1, Decimal("10"), 4, Decimal("0.4"), Decimal("4")),
        obj)
    assert canonical_content_sha256_from_bars(a_price)["canonical_content_sha256"] != da["canonical_content_sha256"]
    a_vol = list(a)
    a_vol[0] = kline_to_canonical(
        KlineRow(start, Decimal("100"), Decimal("110"), Decimal("90"), Decimal("105"),
                 Decimal("2"), start + BAR_MS - 1, Decimal("10"), 4, Decimal("0.4"), Decimal("4")),
        obj)
    assert canonical_content_sha256_from_bars(a_vol)["canonical_content_sha256"] != da["canonical_content_sha256"]
    a_ts = [kline_to_canonical(_kline(start + BAR_MS + i * BAR_MS), obj) for i in range(8)]
    assert canonical_content_sha256_from_bars(a_ts)["canonical_content_sha256"] != da["canonical_content_sha256"]
    from scripts.research.core_btc_binance_v0_materializer_lib import _dec_str, CanonicalContentHasher
    h = CanonicalContentHasher()
    h.add_text(_dec_str(Decimal("1.0")))
    h2 = CanonicalContentHasher()
    h2.add_text(_dec_str(Decimal("1.00")))
    assert h.hexdigest() != h2.hexdigest()
    _place_verified(tmp_path, obj, "\n".join(_row_line(start + i * BAR_MS) for i in range(8)) + "\n")
    materialize_object_1m(tmp_path, obj, audit_raw_object(tmp_path, obj))
    p = canonical_1m_path(tmp_path, obj)
    d1 = canonical_content_sha256_from_parquet(p, batch_size=2)
    d2 = canonical_content_sha256_from_parquet(p, batch_size=7)
    d3 = canonical_content_sha256_from_parquet(tmp_path / "moved.parquet" if False else p, batch_size=3)
    assert d1["canonical_content_sha256"] == d2["canonical_content_sha256"] == d3["canonical_content_sha256"]
    other = tmp_path / "other_dir"
    other.mkdir()
    dest = other / "copy.parquet"
    dest.write_bytes(p.read_bytes())
    assert canonical_content_sha256_from_parquet(dest)["canonical_content_sha256"] == d1["canonical_content_sha256"]
    bars = canonical_rows_from_parquet(p)
    assert canonical_content_sha256_from_bars(bars)["canonical_content_sha256"] == d1["canonical_content_sha256"]


def test_rt_m13_edited_provenance_cannot_bind_parquet_a_to_raw_b(tmp_path: Path):
    objects = _place_all_one_row(tmp_path)
    _materialize_all(tmp_path, objects)
    obj = _daily_obj("2026-08-01")
    parq_sha_a = sha256_of_file(canonical_1m_path(tmp_path, obj))
    from_raw_a = json.loads(canonical_1m_provenance_path(tmp_path, obj).read_text())["canonical_content_sha256"]
    parquet_digest_a = canonical_content_sha256_from_parquet(canonical_1m_path(tmp_path, obj))["canonical_content_sha256"]
    assert from_raw_a == parquet_digest_a
    _place_verified(tmp_path, obj, _row_line(obj.period_start_ms, close="50022") + "\n")
    rec_b = audit_raw_object(tmp_path, obj)
    admitted_b, _ = parse_admit_current_raw(tmp_path, obj)
    digest_b = canonical_content_sha256_from_bars(admitted_b)["canonical_content_sha256"]
    assert digest_b != parquet_digest_a
    prov_path = canonical_1m_provenance_path(tmp_path, obj)
    prov = json.loads(prov_path.read_text())
    prov["source_local_sha256"] = rec_b["local_sha256"]
    prov["source_expected_sha256"] = rec_b["expected_sha256"]
    prov_path.write_text(json.dumps(prov, indent=2, sort_keys=True) + "\n")
    with pytest.raises((StaleCanonicalPartition, StagePreconditionError)):
        verify_canonical_partitions(tmp_path, objects)
    code = mat_cli.main(["--stage", "aggregate", "--dataset-root", str(tmp_path),
                         "--provenance-git-commit-sha", "T"])
    assert code != 0
    code = mat_cli.main(["--stage", "finalize", "--dataset-root", str(tmp_path),
                         "--provenance-git-commit-sha", "T"])
    assert code != 0
    assert not (tmp_path / "reports" / "snapshot_manifest.json").exists()
    assert sha256_of_file(canonical_1m_path(tmp_path, obj)) == parq_sha_a


def _rewrite_prov(tmp_path, obj, **fields):
    path = canonical_1m_provenance_path(tmp_path, obj)
    prov = json.loads(path.read_text())
    prov.update(fields)
    path.write_text(json.dumps(prov, indent=2, sort_keys=True) + "\n")


def test_rt_m13_provenance_field_and_copy_attacks(tmp_path: Path):
    objects = _place_all_one_row(tmp_path)
    _materialize_all(tmp_path, objects)
    jan = _monthly_obj("2020-01")
    feb = _monthly_obj("2020-02")
    daily = _daily_obj("2026-08-01")

    _rewrite_prov(tmp_path, jan, admitted_rows=999999, row_count=999999)
    with pytest.raises((StaleCanonicalPartition, StagePreconditionError)):
        verify_canonical_partitions(tmp_path, objects)
    _materialize_all(tmp_path, objects)

    _rewrite_prov(tmp_path, jan, first_open_time_ms=0, last_open_time_ms=1)
    with pytest.raises((StaleCanonicalPartition, StagePreconditionError)):
        verify_canonical_partitions(tmp_path, objects)
    _materialize_all(tmp_path, objects)

    _rewrite_prov(tmp_path, jan, source_period="2020-02")
    with pytest.raises((StaleCanonicalPartition, StagePreconditionError)):
        verify_canonical_partitions(tmp_path, objects)
    _materialize_all(tmp_path, objects)

    _rewrite_prov(tmp_path, jan, archive_class="daily")
    with pytest.raises((StaleCanonicalPartition, StagePreconditionError)):
        verify_canonical_partitions(tmp_path, objects)
    _materialize_all(tmp_path, objects)

    _rewrite_prov(tmp_path, jan, materializer_version=MATERIALIZER_VERSION + 1)
    with pytest.raises((StaleCanonicalPartition, StagePreconditionError)):
        verify_canonical_partitions(tmp_path, objects)
    _materialize_all(tmp_path, objects)

    _rewrite_prov(tmp_path, jan, canonical_schema_version=CANONICAL_SCHEMA_VERSION + 1)
    with pytest.raises((StaleCanonicalPartition, StagePreconditionError)):
        verify_canonical_partitions(tmp_path, objects)
    _materialize_all(tmp_path, objects)

    _rewrite_prov(tmp_path, jan, parser_version=CANONICALIZATION_VERSION + 1,
                  canonicalization_version=CANONICALIZATION_VERSION + 1)
    with pytest.raises((StaleCanonicalPartition, StagePreconditionError)):
        verify_canonical_partitions(tmp_path, objects)
    _materialize_all(tmp_path, objects)

    pa, pb = canonical_1m_provenance_path(tmp_path, jan), canonical_1m_provenance_path(tmp_path, feb)
    ta, tb = pa.read_text(), pb.read_text()
    pa.write_text(tb)
    pb.write_text(ta)
    with pytest.raises((StaleCanonicalPartition, StagePreconditionError)):
        verify_canonical_partitions(tmp_path, objects)
    _materialize_all(tmp_path, objects)

    canonical_1m_path(tmp_path, feb).write_bytes(canonical_1m_path(tmp_path, jan).read_bytes())
    with pytest.raises((StaleCanonicalPartition, StagePreconditionError)):
        verify_canonical_partitions(tmp_path, objects)
    _materialize_all(tmp_path, objects)

    canonical_1m_path(tmp_path, jan).write_bytes(canonical_1m_path(tmp_path, daily).read_bytes())
    with pytest.raises((StaleCanonicalPartition, StagePreconditionError)):
        verify_canonical_partitions(tmp_path, objects)
    _materialize_all(tmp_path, objects)

    import pyarrow.parquet as pq
    import pyarrow as pa
    path = canonical_1m_path(tmp_path, daily)
    table = pq.read_table(path)
    close = table.column("close").to_pylist()
    close[0] = "50099"
    arrays = {name: table.column(name) for name in table.column_names}
    arrays["close"] = pa.array(close, type=pa.string())
    pq.write_table(pa.table(arrays), path, compression="zstd")
    with pytest.raises((StaleCanonicalPartition, StagePreconditionError)):
        verify_canonical_partitions(tmp_path, objects)
    _materialize_all(tmp_path, objects)

    path = canonical_1m_path(tmp_path, daily)
    table = pq.read_table(path)
    buf = pa.BufferOutputStream()
    pq.write_table(table, buf, compression="zstd", use_dictionary=True, write_statistics=True)
    path.write_bytes(buf.getvalue().to_pybytes())
    with pytest.raises((StaleCanonicalPartition, StagePreconditionError)):
        verify_canonical_partitions(tmp_path, objects)


def test_rt_m13_positive_raw_parquet_digest_and_happy_path(tmp_path: Path):
    objects = _place_all_one_row(tmp_path)
    _materialize_all(tmp_path, objects)
    for obj in objects[:3]:
        admitted, _ = parse_admit_current_raw(tmp_path, obj)
        raw_d = canonical_content_sha256_from_bars(admitted)["canonical_content_sha256"]
        pq_d = canonical_content_sha256_from_parquet(canonical_1m_path(tmp_path, obj))["canonical_content_sha256"]
        assert raw_d == pq_d
    verify_canonical_partitions(tmp_path, objects)
    assert mat_cli.main(["--stage", "aggregate", "--dataset-root", str(tmp_path),
                         "--provenance-git-commit-sha", "T"]) == 0
    assert mat_cli.main(["--stage", "finalize", "--dataset-root", str(tmp_path),
                         "--provenance-git-commit-sha", "T"]) == 0
    cand = json.loads((tmp_path / "manifests" / "CORE_BTC_BINANCE_V0.candidate.json").read_text())
    snap = json.loads((tmp_path / "reports" / "snapshot_manifest.json").read_text())
    assert snap["snapshot_id"]
    assert cand["status"] == "MATERIALIZED_UNVERIFIED"
    assert cand["research_authorized"] is False
