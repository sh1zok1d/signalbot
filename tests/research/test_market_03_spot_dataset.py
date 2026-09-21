"""MARKET-03 spot dataset + funding provenance tests.

Network-free. Does not run EmaCross/EmaCrossFunding or compute strategy
outcomes.
"""
from __future__ import annotations

import json
import zipfile
from io import BytesIO
from pathlib import Path

import pytest

from scripts.research.market_03_binance_spot_btcusdt_1h_v0_lib import (
    DATASET_ID,
    END_EXCLUSIVE,
    FORBIDDEN_MARKET_SUBSTITUTES,
    PROTECTED_OOS_START_MS,
    START_INCLUSIVE,
    STRICT_HISTORICAL_PUBLICATION_LATENCY,
    acquisition_months,
    archive_urls,
    assert_no_strategy_quantities,
    audit_spot_rows,
    build_spot_identity_payload,
    canonical_jsonl_bytes,
    compare_funding_records,
    compare_vision_zips_to_b2_06,
    evaluate_checksum_verification,
    expected_dataset_hour_count,
    expected_hourly_open_times_ms,
    extract_b2_06_funding_container_hashes,
    freqtrade_date_from_open_time_ms,
    funding_archive_urls,
    iso_utc_from_ms,
    kline_mapping_record,
    parse_checksum_text,
    parse_rest_funding_records,
    parse_spot_kline_csv,
    parse_vision_funding_csv,
    read_zip_csv_member,
    refuse_protected_oos_month,
    rest_funding_query_bounds,
    sha256_of_canonical_identity_payload,
    snapshot_from_payload,
    warmup_open_time_ms,
    Market03SpotDatasetError,
)

REPO = Path(__file__).resolve().parents[2]


def test_acquisition_window_excludes_protected_oos_and_covers_ema_warmup():
    months = acquisition_months()
    assert months[0] == "2019-08"
    assert months[-1] == "2024-12"
    assert "2025-01" not in months
    assert "2026-01" not in months
    with pytest.raises(Market03SpotDatasetError):
        refuse_protected_oos_month("2025-01")
    with pytest.raises(Market03SpotDatasetError):
        archive_urls("2025-06")
    with pytest.raises(Market03SpotDatasetError):
        funding_archive_urls("2026-01")
    warmup = warmup_open_time_ms()
    assert iso_utc_from_ms(warmup) == "2019-08-07T20:00:00Z"
    assert START_INCLUSIVE == "2019-08-01T00:00:00Z"
    assert END_EXCLUSIVE == "2025-01-01T00:00:00Z"
    first_aug = expected_hourly_open_times_ms("2019-08")[0]
    assert first_aug <= warmup
    assert expected_dataset_hour_count() == 47520


def test_spot_urls_are_binance_vision_spot_not_futures():
    zip_url, checksum_url = archive_urls("2019-08")
    assert zip_url == (
        "https://data.binance.vision/data/spot/monthly/klines/"
        "BTCUSDT/1h/BTCUSDT-1h-2019-08.zip"
    )
    assert checksum_url.endswith(".CHECKSUM")
    assert "/futures/" not in zip_url
    assert "USD_M_PERPETUAL" in FORBIDDEN_MARKET_SUBSTITUTES
    assert "CORE_BTC_BINANCE_V0" in FORBIDDEN_MARKET_SUBSTITUTES


def test_checksum_and_zip_member_identity():
    parsed = parse_checksum_text(
        "50b058b5774190b577f1bc45767aeb33f4e947dc00e8d143f6c4afa0f5a3cd34  "
        "BTCUSDT-1h-2019-08.zip\n"
    )
    assert parsed["sha256"].startswith("50b058b5")
    assert parsed["filename"] == "BTCUSDT-1h-2019-08.zip"
    assert (
        evaluate_checksum_verification(
            parsed["sha256"], parsed, "BTCUSDT-1h-2019-08.zip"
        )
        == "VERIFIED"
    )
    assert (
        evaluate_checksum_verification(
            parsed["sha256"], parsed, "BTCUSDT-1h-2019-09.zip"
        )
        == "FILENAME_IDENTITY_MISMATCH"
    )
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w") as archive:
        archive.writestr("BTCUSDT-1h-2019-08.csv", "not-the-point\n")
    text, names, status = read_zip_csv_member(buf.getvalue(), "BTCUSDT-1h-2019-08.csv")
    assert status == "OK"
    assert names == ["BTCUSDT-1h-2019-08.csv"]
    assert text is not None
    missing = read_zip_csv_member(buf.getvalue(), "wrong.csv")
    assert missing[2] == "MISSING_EXPECTED_CSV_MEMBER"


def test_parse_and_audit_native_1h_kline():
    csv_text = (
        "1564617600000,10000,10100,9900,10050,1.5,1564621199999,15000,10,0.7,7000,0\n"
        "1564621200000,10050,10200,10000,10100,2.0,1564624799999,20000,12,1.0,10000,0\n"
    )
    rows, meta = parse_spot_kline_csv(csv_text)
    assert meta["malformed_row_count"] == 0
    assert len(rows) == 2
    assert rows[0].open_time_ms == 1564617600000
    assert freqtrade_date_from_open_time_ms(rows[0].open_time_ms) == "2019-08-01T00:00:00Z"
    audit = audit_spot_rows(
        rows, expected_open_times=[1564617600000, 1564621200000]
    )
    assert audit["missing_count"] == 0
    assert audit["duplicate_count"] == 0
    assert audit["schema_ok"] is True
    gapped = audit_spot_rows(
        rows, expected_open_times=[1564617600000, 1564621200000, 1564624800000]
    )
    assert gapped["missing_count"] == 1
    payload = json.loads(canonical_jsonl_bytes(rows).splitlines()[0])
    assert payload["open"] == "10000"
    assert "ignore" not in payload


def test_parse_rejects_protected_oos_row():
    oos = str(PROTECTED_OOS_START_MS)
    csv_text = (
        f"{oos},10000,10100,9900,10050,1.5,{int(oos)+3599999},15000,10,0.7,7000,0\n"
    )
    with pytest.raises(Market03SpotDatasetError):
        parse_spot_kline_csv(csv_text)


def test_kline_mapping_documents_open_time_as_freqtrade_date():
    mapping = kline_mapping_record()
    assert mapping["freqtrade_dataframe_date"] == "candle_open_utc_equal_to_open_time"
    assert mapping["binance_open_time_semantic"] == "candle_open_utc_ms"
    assert mapping["documented_api_origin"] == "/api/v3/klines"
    assert "CORE_BTC_BINANCE_V0" in mapping["core_derived_1h_forbidden"]


def test_funding_rest_bounds_stop_before_2025_and_vision_vs_rest_compare():
    bounds = rest_funding_query_bounds()
    assert bounds["path"] == "/fapi/v1/fundingRate"
    assert bounds["fallback_endpoint"].endswith("/fapi/v1/fundingRate")
    assert bounds["endTime_exclusive_ms"] == PROTECTED_OOS_START_MS
    assert bounds["startTime_ms"] < PROTECTED_OOS_START_MS
    rest = parse_rest_funding_records(
        [
            {"fundingTime": 1572580800000, "fundingRate": "0.0001", "symbol": "BTCUSDT"},
            {"fundingTime": 1572609600001, "fundingRate": "0.0002", "symbol": "BTCUSDT"},
            {
                "fundingTime": PROTECTED_OOS_START_MS,
                "fundingRate": "0.0099",
                "symbol": "BTCUSDT",
            },
        ]
    )
    assert len(rest) == 2
    vision_csv = (
        "calc_time,funding_interval_hours,last_funding_rate\n"
        "1572580800000,8,0.0001\n"
        "1572609600000,8,0.0002\n"
    )
    vision, meta = parse_vision_funding_csv(vision_csv)
    assert meta["header_present"] is True
    compared = compare_funding_records(rest, vision)
    assert compared["hour_bucket_rate_equal_count"] == 2
    assert compared["semantic_rate_equivalence_on_hour_buckets"] is True
    assert compared["rest_nonzero_ms_residual_count"] == 1
    assert compared["not_the_same_frozen_object"] is True
    assert compared["protected_oos_compared"] is False


def test_b2_06_container_hash_compare_and_snapshot_identity():
    ledger = {
        "objects": [
            {
                "series": "funding",
                "period": "2020-09",
                "container_sha256": "aa" * 32,
                "container_bytes": 10,
                "min_source_timestamp_ms": 1598918400000,
            },
            {
                "series": "oi",
                "period": "2020-09",
                "container_sha256": "bb" * 32,
            },
        ]
    }
    by_period = extract_b2_06_funding_container_hashes(ledger)
    assert list(by_period) == ["2020-09"]
    compared = compare_vision_zips_to_b2_06(
        [{"period": "2020-09", "container_sha256": "aa" * 32, "container_bytes": 10}],
        by_period,
    )
    assert compared["all_overlapping_containers_byte_identical"] is True
    payload = build_spot_identity_payload(
        source_object_identities=[{"source_period": "2019-08", "local_sha256": "ab"}],
        canonical_klines_sha256="cd",
        canonical_row_count=1,
        gap_count=0,
        duplicate_count=0,
        construction_code_sha256={"scripts/x.py": "ef"},
        provenance_git_commit_sha="deadbeef",
    )
    snap = snapshot_from_payload(payload)
    assert snap["snapshot_id"] == sha256_of_canonical_identity_payload(payload)
    assert payload["dataset_id"] == DATASET_ID
    assert payload["market_03_scientifically_bound"] is False
    assert payload["market_type"] == "SPOT"


def test_lib_refuses_strategy_quantity_names():
    with pytest.raises(Market03SpotDatasetError):
        assert_no_strategy_quantities(["row_count", "equity_curve"])
    assert_no_strategy_quantities(["row_count", "gap_count"])
    assert STRICT_HISTORICAL_PUBLICATION_LATENCY == "UNPROVEN"


def test_b2_06_ledger_file_is_present_for_hash_compare():
    path = REPO / (
        "docs/research_data/B2_06_BINANCE_UM_BTCUSDT_OI_FUNDING_V0/"
        "OBJECT_LEDGER_5a9d036b.json"
    )
    assert path.is_file()
    text = path.read_text(encoding="utf-8")
    assert "BTCUSDT-fundingRate-2020-09.zip" in text
