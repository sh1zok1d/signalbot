"""Network-free tests for the CORE_BTC_BINANCE_V0 materializer.

Fixtures are local synthetic ZIP+CHECKSUM pairs. No Binance HTTP.
"""
from __future__ import annotations

import io
import json
import zipfile
from decimal import Decimal
from pathlib import Path

import pytest

import scripts.research.core_btc_binance_v0_materializer as mat_cli
from scripts.research.core_btc_binance_v0_materializer_lib import (
    BAR_MS,
    DATASET_ID,
    MATERIALIZER_VERSION,
    REPO_MANIFEST_PATH,
    SourceObject,
    acquire_one_object,
    aggregate_htf,
    assert_disk_budget,
    atomic_write_bytes,
    audit_raw_object,
    bars_available_at_1m,
    bars_available_at_htf,
    build_frozen_source_plan,
    build_snapshot_identity,
    canonical_1m_path,
    canonical_rows_from_parquet,
    continuity_audit,
    dumps_deterministic,
    expected_global_minute_count,
    frozen_range_ms,
    gap_extreme_diagnostic,
    htf_from_parquet,
    kline_to_canonical,
    load_all_canonical_1m,
    materialize_object_1m,
    merge_cross_object,
    plan_report,
    remaining_extracted_csvs,
    raw_checksum_path,
    raw_zip_path,
)
from scripts.research.core_btc_binance_v0_probe_lib import (
    KlineRow,
    day_bounds_ms,
    evaluate_checksum_verification,
    month_bounds_ms,
    parse_checksum_text,
    sha256_of_bytes,
    sha256_of_file,
)


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
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr(member_name, csv_text)
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


def _kline(open_time_ms: int) -> KlineRow:
    return KlineRow(
        open_time_ms, Decimal("100"), Decimal("110"), Decimal("90"), Decimal("105"),
        Decimal("1"), open_time_ms + BAR_MS - 1, Decimal("10"), 4,
        Decimal("0.4"), Decimal("4"),
    )


# ---------------------------------------------------------------------------
# 1-3 plan
# ---------------------------------------------------------------------------
def test_frozen_source_plan_monthly_then_daily_exact_counts_and_order():
    objects = build_frozen_source_plan()
    monthly = [o for o in objects if o.archive_class == "monthly"]
    daily = [o for o in objects if o.archive_class == "daily"]
    assert [o.source_period for o in monthly][0] == "2020-01"
    assert [o.source_period for o in monthly][-1] == "2026-07"
    assert len(monthly) == 79
    assert [o.source_period for o in daily][0] == "2026-08-01"
    assert [o.source_period for o in daily][-1] == "2026-08-25"
    assert len(daily) == 25
    assert len(objects) == 104
    assert [o.source_period for o in objects] == sorted(
        [o.source_period for o in monthly],
    ) + sorted(o.source_period for o in daily)
    assert objects[0].source_url.endswith("monthly/klines/BTCUSDT/1m/BTCUSDT-1m-2020-01.zip")
    assert objects[-1].source_url.endswith("daily/klines/BTCUSDT/1m/BTCUSDT-1m-2026-08-25.zip")
    assert objects[-1].expected_csv_member_name == "BTCUSDT-1m-2026-08-25.csv"
    report = plan_report(objects, git_commit_sha="TEST")
    serialized = dumps_deterministic(report)
    assert serialized == dumps_deterministic(json.loads(serialized))
    start, end = frozen_range_ms()
    assert start == 1577836800000
    assert end == 1787702400000  # 2026-08-26T00:00:00Z
    assert expected_global_minute_count() == (end - start) // BAR_MS


def test_cli_plan_writes_report_and_does_not_touch_repo_manifest(tmp_path: Path):
    repo_manifest = Path("/tmp/signalbot") / REPO_MANIFEST_PATH
    before = repo_manifest.read_bytes()
    root = tmp_path / "ds"
    code = mat_cli.main(["--stage", "plan", "--dataset-root", str(root),
                         "--provenance-git-commit-sha", "TESTSHA"])
    assert code == 0
    plan = json.loads((root / "reports" / "source_plan.json").read_text())
    assert plan["source_object_count"] == 104
    assert plan["monthly_range"]["count"] == 79
    assert plan["daily_range"]["count"] == 25
    assert repo_manifest.read_bytes() == before


def test_cli_acquire_refuses_without_allow_flag(tmp_path: Path):
    assert mat_cli.main(["--stage", "acquire", "--dataset-root", str(tmp_path)]) == 2


# ---------------------------------------------------------------------------
# checksum / revision / part files
# ---------------------------------------------------------------------------
def test_verified_object_is_admitted(tmp_path: Path):
    obj = _daily_obj("2026-08-01")
    start, _ = day_bounds_ms("2026-08-01")
    digest = _place_verified(tmp_path, obj, _row_line(start) + "\n")
    rec = audit_raw_object(tmp_path, obj)
    assert rec["checksum_verification"] == "VERIFIED"
    assert rec["checksum_observed_filename"] == obj.expected_zip_filename
    assert rec["local_sha256"] == digest
    assert rec["admitted_to_canonical"] is True
    assert rec["parser_status"] == "OK"


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
    parsed = parse_checksum_text(raw_checksum_path(tmp_path, obj).read_text())
    assert evaluate_checksum_verification(
        sha256_of_file(raw_zip_path(tmp_path, obj)), parsed, obj.expected_zip_filename,
    ) == "FILENAME_IDENTITY_MISMATCH"


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
    assert raw_zip_path(tmp_path, obj).exists()


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
    daily = _daily_obj("2026-08-01")
    assert monthly.expected_csv_member_name == "BTCUSDT-1m-2026-07.csv"
    assert daily.expected_csv_member_name == "BTCUSDT-1m-2026-08-01.csv"
    start, _ = month_bounds_ms("2026-07")
    zip_bytes = _make_zip_bytes("BTCUSDT-1m-2026-07-01.csv", _row_line(start) + "\n")
    atomic_write_bytes(raw_zip_path(tmp_path, monthly), zip_bytes)
    atomic_write_bytes(
        raw_checksum_path(tmp_path, monthly),
        _checksum_text(sha256_of_bytes(zip_bytes), monthly.expected_zip_filename).encode())
    rec = audit_raw_object(tmp_path, monthly)
    assert rec["parser_status"] == "MISSING_EXPECTED_CSV_MEMBER"


# ---------------------------------------------------------------------------
# parse / invariants / boundaries
# ---------------------------------------------------------------------------
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
    assert rec["malformed_row_count"] == 3  # NaN/Inf at parse, plus short row
    mat = materialize_object_1m(tmp_path, obj, rec)
    assert mat["admitted_rows"] == 1
    assert mat["rejected_schema"] == 3


def test_minute_alignment_rejected(tmp_path: Path):
    obj = _daily_obj("2026-08-01")
    start, _ = day_bounds_ms("2026-08-01")
    csv = _row_line(start + 1) + "\n"
    _place_verified(tmp_path, obj, csv)
    rec = audit_raw_object(tmp_path, obj)
    assert rec["invariant_violation_count"] == 1
    mat = materialize_object_1m(tmp_path, obj, rec)
    assert mat["admitted_rows"] == 0
    assert mat["rejected_invariant"] == 1


def test_monthly_to_daily_boundary_is_continuous(tmp_path: Path):
    monthly = _monthly_obj("2026-07")
    daily = _daily_obj("2026-08-01")
    july_start, july_end = month_bounds_ms("2026-07")
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
    assert bars[1].archive_class == "daily"


def test_end_exclusive_2026_08_26_never_enters_dataset(tmp_path: Path):
    obj = _daily_obj("2026-08-25")
    start, end = day_bounds_ms("2026-08-25")
    last_ok = end - BAR_MS
    forbidden_start, _ = frozen_range_ms()[1], None
    forbidden = frozen_range_ms()[1]  # 2026-08-26 00:00
    csv = _row_line(last_ok) + "\n" + _row_line(forbidden) + "\n"
    _place_verified(tmp_path, obj, csv)
    rec = audit_raw_object(tmp_path, obj)
    mat = materialize_object_1m(tmp_path, obj, rec)
    bars = canonical_rows_from_parquet(canonical_1m_path(tmp_path, obj))
    assert all(b.open_time_ms < forbidden for b in bars)
    assert last_ok in {b.open_time_ms for b in bars}
    assert mat["rejected_identity"] + mat["rejected_end_exclusive"] >= 1


def test_identical_vs_conflicting_duplicates(tmp_path: Path):
    obj = _daily_obj("2026-08-01")
    start, _ = day_bounds_ms("2026-08-01")
    identical = _row_line(start)
    conflict = _row_line(start + BAR_MS, close="50051")
    conflict2 = _row_line(start + BAR_MS, close="50052")
    csv = "\n".join([identical, identical, conflict, conflict2]) + "\n"
    _place_verified(tmp_path, obj, csv)
    rec = audit_raw_object(tmp_path, obj)
    assert rec["duplicate_count"] >= 2
    mat = materialize_object_1m(tmp_path, obj, rec)
    assert mat["identical_duplicate_count"] == 1
    assert mat["conflicting_duplicate_open_times"] == [start + BAR_MS]
    bars = canonical_rows_from_parquet(canonical_1m_path(tmp_path, obj))
    assert [b.open_time_ms for b in bars] == [start]


def test_cross_object_overlap_conflict(tmp_path: Path):
    a = _daily_obj("2026-08-01")
    b = _daily_obj("2026-08-02")
    t, _ = day_bounds_ms("2026-08-01")
    _place_verified(tmp_path, a, _row_line(t, close="50050") + "\n")
    # place the same timestamp into the next day's zip (packaging overlap)
    zip_bytes = _make_zip_bytes(b.expected_csv_member_name, _row_line(t, close="50099") + "\n")
    atomic_write_bytes(raw_zip_path(tmp_path, b), zip_bytes)
    atomic_write_bytes(
        raw_checksum_path(tmp_path, b),
        _checksum_text(sha256_of_bytes(zip_bytes), b.expected_zip_filename).encode())
    ra, rb = audit_raw_object(tmp_path, a), audit_raw_object(tmp_path, b)
    materialize_object_1m(tmp_path, a, ra)
    # day-2 materialize will reject identity (outside its day bounds)
    mb = materialize_object_1m(tmp_path, b, rb)
    assert mb["rejected_identity"] == 1
    # force a canonical partition that contains the overlapping bar
    from scripts.research.core_btc_binance_v0_materializer_lib import CanonicalBar, canonical_rows_to_parquet_bytes
    foreign = kline_to_canonical(_kline(t), b, "deadbeef")
    foreign = CanonicalBar(**{**foreign.__dict__, "close": Decimal("50099")})
    atomic_write_bytes(canonical_1m_path(tmp_path, b), canonical_rows_to_parquet_bytes([foreign]))
    merged, stats = merge_cross_object(load_all_canonical_1m(tmp_path, [a, b]))
    assert stats["cross_object_conflicting_duplicate_count"] == 1
    assert merged == []


def test_one_missing_minute_and_contiguous_gap_and_by_month(tmp_path: Path):
    start = 1577836800000  # 2020-01-01
    bars = [kline_to_canonical(_kline(start + i * BAR_MS), _monthly_obj("2020-01"), "x")
            for i in (0, 1, 4, 5)]  # missing 2,3 (contiguous) — wait 2 minutes missing
    # actually minutes 2 and 3 missing between 1 and 4
    window_end = start + 6 * BAR_MS
    audit = continuity_audit(bars, start_ms=start, end_ms=window_end)
    assert audit["missing_minute_count"] == 2
    assert audit["gaps"][0]["missing_minutes"] == 2
    assert audit["gaps"][0]["start_ms"] == start + 2 * BAR_MS
    assert audit["gaps"][0]["end_exclusive_ms"] == start + 4 * BAR_MS
    assert audit["missingness_by_year"]["2020"] == 2
    assert audit["missingness_by_month"]["2020-01"] == 2
    # no synthetic repair: canonical list still length 4
    assert audit["observed_unique_timestamps"] == 4


def test_no_synthetic_gap_repair_in_materialize(tmp_path: Path):
    obj = _daily_obj("2026-08-01")
    start, _ = day_bounds_ms("2026-08-01")
    _place_verified(tmp_path, obj, _row_line(start) + "\n")
    rec = audit_raw_object(tmp_path, obj)
    materialize_object_1m(tmp_path, obj, rec)
    bars = canonical_rows_from_parquet(canonical_1m_path(tmp_path, obj))
    assert len(bars) == 1
    assert bars[0].open_time_ms == start


def test_canonical_order_and_repeated_materialization_deterministic(tmp_path: Path):
    obj = _daily_obj("2026-08-01")
    start, _ = day_bounds_ms("2026-08-01")
    csv = _row_line(start + BAR_MS) + "\n" + _row_line(start) + "\n"
    _place_verified(tmp_path, obj, csv)
    rec = audit_raw_object(tmp_path, obj)
    materialize_object_1m(tmp_path, obj, rec)
    path = canonical_1m_path(tmp_path, obj)
    first = sha256_of_file(path)
    bars = canonical_rows_from_parquet(path)
    assert [b.open_time_ms for b in bars] == [start, start + BAR_MS]
    rec2 = audit_raw_object(tmp_path, obj)
    out = materialize_object_1m(tmp_path, obj, rec2)
    assert out["status"] == "REUSED_IDENTICAL_PARTITION"
    assert sha256_of_file(path) == first


def test_parquet_decimal_round_trip(tmp_path: Path):
    obj = _daily_obj("2026-08-01")
    start, _ = day_bounds_ms("2026-08-01")
    _place_verified(tmp_path, obj, _row_line(
        start, open_="7189.43", high="7190.52", low="7177", close="7182.44", volume="246.092") + "\n")
    rec = audit_raw_object(tmp_path, obj)
    materialize_object_1m(tmp_path, obj, rec)
    bar = canonical_rows_from_parquet(canonical_1m_path(tmp_path, obj))[0]
    assert bar.open == Decimal("7189.43")
    assert bar.base_volume == Decimal("246.092")
    assert bar.taker_sell_base_volume == bar.base_volume - bar.taker_buy_base_volume


# ---------------------------------------------------------------------------
# HTF / lookahead / snapshot
# ---------------------------------------------------------------------------
def _n_bars(n: int, start: int, obj: SourceObject) -> list:
    return [kline_to_canonical(_kline(start + i * BAR_MS), obj, "x") for i in range(n)]


def test_htf_5m_15m_1h_4h_complete_and_incomplete():
    obj = _monthly_obj("2020-01")
    start, _ = month_bounds_ms("2020-01")
    complete_4h = _n_bars(240, start, obj)
    rows_5 = aggregate_htf(complete_4h, 5, start_ms=start, end_ms=start + 240 * BAR_MS)
    rows_15 = aggregate_htf(complete_4h, 15, start_ms=start, end_ms=start + 240 * BAR_MS)
    rows_1h = aggregate_htf(complete_4h, 60, start_ms=start, end_ms=start + 240 * BAR_MS)
    rows_4h = aggregate_htf(complete_4h, 240, start_ms=start, end_ms=start + 240 * BAR_MS)
    assert len(rows_5) == 48 and all(r.is_complete for r in rows_5)
    assert len(rows_15) == 16 and all(r.is_complete for r in rows_15)
    assert len(rows_1h) == 4 and all(r.is_complete for r in rows_1h)
    assert len(rows_4h) == 1 and rows_4h[0].is_complete
    assert rows_4h[0].open == complete_4h[0].open
    assert rows_4h[0].close == complete_4h[-1].close
    assert rows_4h[0].high == max(b.high for b in complete_4h)
    assert rows_4h[0].trade_count == sum(b.trade_count for b in complete_4h)
    assert rows_4h[0].available_at_ms == start + 240 * BAR_MS
    assert rows_5[0].open_time_ms == start
    assert start % (5 * BAR_MS) == 0

    incomplete = complete_4h[:-1]  # drop last minute
    bad_5 = aggregate_htf(incomplete, 5, start_ms=start, end_ms=start + 240 * BAR_MS)
    bad_4h = aggregate_htf(incomplete, 240, start_ms=start, end_ms=start + 240 * BAR_MS)
    assert bad_5[-1].is_complete is False
    assert bad_5[-1].open is None
    assert bad_4h[0].is_complete is False
    assert bad_4h[0].close is None
    assert all(r.is_complete for r in bad_5[:-1])


def test_incomplete_htf_does_not_leak_partial_ohlc():
    obj = _monthly_obj("2020-01")
    start, _ = month_bounds_ms("2020-01")
    bars = _n_bars(4, start, obj)  # 4 of 5
    rows = aggregate_htf(bars, 5, start_ms=start, end_ms=start + 5 * BAR_MS)
    assert len(rows) == 1
    assert rows[0].is_complete is False
    assert rows[0].observed_constituents == 4
    for name in ("open", "high", "low", "close", "base_volume"):
        assert getattr(rows[0], name) is None


def test_no_lookahead_1m_and_htf():
    obj = _monthly_obj("2020-01")
    start, _ = month_bounds_ms("2020-01")
    bars = _n_bars(5, start, obj)
    T = start + BAR_MS  # first bar just closed
    eligible = bars_available_at_1m(bars, T)
    assert [b.open_time_ms for b in eligible] == [start]
    assert all(b.available_at_ms == b.open_time_ms + BAR_MS for b in bars)
    htf = aggregate_htf(bars, 5, start_ms=start, end_ms=start + 5 * BAR_MS)
    assert bars_available_at_htf(htf, start + 4 * BAR_MS) == []  # bucket not closed
    closed = bars_available_at_htf(htf, start + 5 * BAR_MS)
    assert len(closed) == 1 and closed[0].is_complete


def test_snapshot_id_stable_and_changes_with_checksum_or_version():
    objects = build_frozen_source_plan()[:2]
    inventory = [
        {"source_period": o.source_period, "archive_class": o.archive_class,
         "source_url": o.source_url, "local_sha256": "aa" * 32,
         "expected_sha256": "aa" * 32, "checksum_verification": "VERIFIED",
         "byte_size": 10}
        for o in objects
    ]
    a = build_snapshot_identity(
        objects=objects, inventory=inventory, quality_report_sha256="q1",
        output_checksums={"canonical/1m/x.parquet": "bb" * 32},
        contract_sha256="cc" * 32, git_commit_sha="deadbeef")
    b = build_snapshot_identity(
        objects=objects, inventory=inventory, quality_report_sha256="q1",
        output_checksums={"canonical/1m/x.parquet": "bb" * 32},
        contract_sha256="cc" * 32, git_commit_sha="deadbeef")
    assert a["snapshot_id"] == b["snapshot_id"]
    inventory2 = [{**inventory[0], "local_sha256": "dd" * 32}, inventory[1]]
    c = build_snapshot_identity(
        objects=objects, inventory=inventory2, quality_report_sha256="q1",
        output_checksums={"canonical/1m/x.parquet": "bb" * 32},
        contract_sha256="cc" * 32, git_commit_sha="deadbeef")
    assert c["snapshot_id"] != a["snapshot_id"]
    # materializer version is inside identity payload
    payload = a["identity_payload"]
    assert payload["materializer_version"] == MATERIALIZER_VERSION
    payload_changed = dict(payload)
    payload_changed["materializer_version"] = MATERIALIZER_VERSION + 1
    from scripts.research.core_btc_binance_v0_materializer_lib import sha256_of_canonical_identity_payload
    assert sha256_of_canonical_identity_payload(payload_changed) != a["snapshot_id"]


def test_atomic_output_adoption_and_no_permanent_csv(tmp_path: Path):
    obj = _daily_obj("2026-08-01")
    start, _ = day_bounds_ms("2026-08-01")
    _place_verified(tmp_path, obj, _row_line(start) + "\n")
    rec = audit_raw_object(tmp_path, obj)
    materialize_object_1m(tmp_path, obj, rec)
    assert remaining_extracted_csvs(tmp_path) == []
    assert canonical_1m_path(tmp_path, obj).suffix == ".parquet"
    assert not list(tmp_path.rglob("*.part"))


def test_disk_safety_gate(tmp_path: Path):
    usage = assert_disk_budget(tmp_path, estimated_download_bytes=1, disk_reserve_bytes=1)
    assert usage["disk_safety_ok"] is True
    with pytest.raises(Exception):
        assert_disk_budget(tmp_path, estimated_download_bytes=10**18, disk_reserve_bytes=10**18)


def test_gap_extreme_diagnostic_is_deterministic_and_does_not_repair():
    obj = _monthly_obj("2020-01")
    start, _ = month_bounds_ms("2020-01")
    bars = _n_bars(3, start, obj)
    # inject a huge-volume bar adjacent to a gap
    bars[0] = kline_to_canonical(
        KlineRow(start, Decimal("100"), Decimal("110"), Decimal("90"), Decimal("200"),
                 Decimal("999999"), start + BAR_MS - 1, Decimal("10"), 4,
                 Decimal("0.4"), Decimal("4")),
        obj, "x")
    audit = continuity_audit(bars, start_ms=start, end_ms=start + 5 * BAR_MS)
    assert audit["missing_minute_count"] == 2
    diag = gap_extreme_diagnostic(bars, audit["gaps"])
    assert "99th percentile" in diag["rule"]
    diag2 = gap_extreme_diagnostic(bars, audit["gaps"])
    assert dumps_deterministic(diag) == dumps_deterministic(diag2)
    assert audit["observed_unique_timestamps"] == 3  # unrepaired


def test_repo_manifest_path_constant_unpromoted():
    text = Path("/tmp/signalbot/docs/manifests/CORE_BTC_BINANCE_V0.yaml").read_text()
    assert "status: PLANNED_NOT_MATERIALIZED" in text
    assert "research_authorized: false" in text
    assert REPO_MANIFEST_PATH == "docs/manifests/CORE_BTC_BINANCE_V0.yaml"


def test_utc_alignment_and_available_at_never_uses_close_time():
    obj = _monthly_obj("2020-01")
    start, _ = month_bounds_ms("2020-01")
    bar = kline_to_canonical(_kline(start), obj, "x")
    assert bar.available_at_ms == start + BAR_MS
    assert bar.bar_end_exclusive_ms == bar.available_at_ms
    assert bar.available_at_ms != start + BAR_MS - 1  # close_time convention
