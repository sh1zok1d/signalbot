"""Acquire MARKET_03_BINANCE_SPOT_BTCUSDT_1H_V0 and funding provenance.

Downloads official Binance Vision SPOT BTCUSDT 1h monthly klines for
2019-08 through 2024-12, plus USD-M fundingRate objects needed to compare
B2-06 / Vision / REST without opening protected 2025/2026 OOS.

Does not run EmaCross/EmaCrossFunding, compute EMA/funding percentiles,
trades, equity, or any MARKET-03 scientific outcome.
"""
from __future__ import annotations

import argparse
import json
import ssl
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

from scripts.research.market_03_binance_spot_btcusdt_1h_v0_lib import (
    ACQUIRE_END_MONTH_INCLUSIVE,
    ACQUIRE_START_MONTH,
    ARCHIVE_ROOT,
    B2_06_DATASET_ID,
    B2_06_OBJECT_LEDGER,
    B2_06_SNAPSHOT_ID,
    DATASET_ID,
    DOCUMENTED_API_ORIGIN,
    DUPLICATE_POLICY,
    END_EXCLUSIVE,
    FUNDING_PRODUCT,
    FUNDING_REST_ENDPOINT,
    FUNDING_REST_PATH,
    FUNDING_SYMBOL,
    FUNDING_VISION_START_MONTH,
    GAP_POLICY,
    INTERVAL,
    MARKET_TYPE,
    NORMALIZATION_RULES,
    PROTECTED_OOS_START_MS,
    PROVIDER,
    REPRODUCTION_FUNDINGTIME_ASSUMPTION_MEANING,
    START_INCLUSIVE,
    STARTUP_CANDLE_COUNT,
    STRICT_HISTORICAL_PUBLICATION_LATENCY,
    SYMBOL,
    VENUE,
    acquisition_months,
    archive_object_name,
    archive_urls,
    assert_no_strategy_quantities,
    audit_funding_records,
    audit_spot_rows,
    build_spot_identity_payload,
    canonical_jsonl_bytes,
    compare_funding_records,
    compare_vision_zips_to_b2_06,
    dumps_deterministic,
    evaluate_checksum_verification,
    expected_csv_member_name,
    expected_dataset_hour_count,
    expected_hourly_open_times_ms,
    extract_b2_06_funding_container_hashes,
    freqtrade_date_from_open_time_ms,
    funding_archive_object_name,
    funding_archive_urls,
    funding_csv_member_name,
    iso_utc_from_ms,
    iter_year_months,
    kline_mapping_record,
    parse_checksum_text,
    parse_rest_funding_records,
    parse_spot_kline_csv,
    parse_vision_funding_csv,
    read_zip_csv_member,
    rest_funding_query_bounds,
    sha256_of_bytes,
    sha256_of_file,
    snapshot_from_payload,
    warmup_open_time_ms,
)

UTC = timezone.utc
USER_AGENT = "signalbot-research-market-03-data-acquisition/1.0"
DEFAULT_TIMEOUT = 60.0
DEFAULT_RETRIES = 4
SLEEP_BETWEEN_REQUESTS = 0.15

CONSTRUCTION_CODE_PATHS = (
    "scripts/research/market_03_binance_spot_btcusdt_1h_v0_lib.py",
    "scripts/research/market_03_binance_spot_btcusdt_1h_v0_acquire.py",
)


def _now_utc() -> str:
    return datetime.now(tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _ssl_context() -> ssl.SSLContext:
    return ssl.create_default_context()


def http_get(
    url: str,
    *,
    timeout: float = DEFAULT_TIMEOUT,
    retries: int = DEFAULT_RETRIES,
    accept: str = "*/*",
) -> tuple[int, bytes, str]:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": USER_AGENT, "Accept": accept},
        method="GET",
    )
    last_error: Optional[BaseException] = None
    delay = 4.0
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(
                request, timeout=timeout, context=_ssl_context()
            ) as response:
                body = response.read()
                return int(response.status), body, url
        except urllib.error.HTTPError as exc:
            body = exc.read() if exc.fp is not None else b""
            if exc.code in {404, 403} or 400 <= exc.code < 500:
                return int(exc.code), body, url
            last_error = exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_error = exc
        if attempt < retries:
            time.sleep(delay)
            delay *= 2
    raise RuntimeError(f"GET failed for {url}: {last_error}") from last_error


def detect_git_sha(repo_root: Path) -> str:
    head = repo_root / ".git" / "HEAD"
    if not head.exists():
        return "UNKNOWN"
    text = head.read_text(encoding="utf-8").strip()
    if text.startswith("ref:"):
        ref = repo_root / ".git" / text.split(" ", 1)[1].strip()
        if ref.exists():
            return ref.read_text(encoding="utf-8").strip()
    return text


def construction_code_hashes(repo_root: Path) -> dict[str, str]:
    out = {}
    for rel in CONSTRUCTION_CODE_PATHS:
        out[rel] = sha256_of_file(repo_root / rel)
    return out


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dumps_deterministic(payload), encoding="utf-8")


def acquire_spot_month(
    year_month: str,
    raw_dir: Path,
    *,
    timeout: float,
) -> dict[str, Any]:
    zip_url, checksum_url = archive_urls(year_month)
    zip_name = archive_object_name(year_month)
    zip_path = raw_dir / zip_name
    checksum_path = raw_dir / f"{zip_name}.CHECKSUM"
    retrieved_at = _now_utc()
    checksum_status, checksum_body, _ = http_get(checksum_url, timeout=timeout)
    time.sleep(SLEEP_BETWEEN_REQUESTS)
    zip_status, zip_body, _ = http_get(zip_url, timeout=timeout)
    time.sleep(SLEEP_BETWEEN_REQUESTS)
    record: dict[str, Any] = {
        "period": year_month,
        "market_type": MARKET_TYPE,
        "symbol": SYMBOL,
        "interval": INTERVAL,
        "source": "binance_vision_official_archive",
        "documented_api_origin": DOCUMENTED_API_ORIGIN,
        "zip_url": zip_url,
        "checksum_url": checksum_url,
        "request_bounds": {
            "month": year_month,
            "start_inclusive": iso_utc_from_ms(expected_hourly_open_times_ms(year_month)[0]),
            "end_exclusive": iso_utc_from_ms(
                expected_hourly_open_times_ms(year_month)[-1] + 3600_000
            ),
        },
        "retrieval_timestamp_utc": retrieved_at,
        "http_status_zip": zip_status,
        "http_status_checksum": checksum_status,
    }
    if checksum_status == 200:
        checksum_path.write_bytes(checksum_body)
        parsed_checksum = parse_checksum_text(checksum_body.decode("utf-8"))
        record["checksum_sidecar_sha256"] = sha256_of_bytes(checksum_body)
        record["expected_sha256"] = parsed_checksum["sha256"]
        record["checksum_filename"] = parsed_checksum["filename"]
    else:
        parsed_checksum = None
        record["expected_sha256"] = None
        record["checksum_filename"] = None
    if zip_status != 200:
        record["retrieval_status"] = "FETCH_FAILED"
        record["container_sha256"] = None
        return record
    zip_path.write_bytes(zip_body)
    local_sha = sha256_of_bytes(zip_body)
    record["container_bytes"] = len(zip_body)
    record["container_sha256"] = local_sha
    record["checksum_verification"] = evaluate_checksum_verification(
        local_sha, parsed_checksum, zip_name
    )
    csv_text, members, parser_status = read_zip_csv_member(
        zip_body, expected_csv_member_name(year_month)
    )
    record["archive_members"] = members
    record["member_parser_status"] = parser_status
    if csv_text is None:
        record["retrieval_status"] = "MEMBER_REJECTED"
        return record
    record["member_bytes"] = len(csv_text.encode("utf-8"))
    record["member_sha256"] = sha256_of_bytes(csv_text.encode("utf-8"))
    rows, parse_meta = parse_spot_kline_csv(csv_text)
    record.update(parse_meta)
    audit = audit_spot_rows(rows, expected_open_times=expected_hourly_open_times_ms(year_month))
    record["audit"] = audit
    record["rows"] = rows
    record["retrieval_status"] = (
        "ACCEPTED"
        if record["checksum_verification"] == "VERIFIED"
        and parser_status == "OK"
        and parse_meta["malformed_row_count"] == 0
        else "ACCEPTED_WITH_FINDINGS"
    )
    return record


def acquire_funding_month(
    year_month: str,
    raw_dir: Path,
    *,
    timeout: float,
) -> dict[str, Any]:
    zip_url, checksum_url = funding_archive_urls(year_month)
    zip_name = funding_archive_object_name(year_month)
    retrieved_at = _now_utc()
    checksum_status, checksum_body, _ = http_get(checksum_url, timeout=timeout)
    time.sleep(SLEEP_BETWEEN_REQUESTS)
    zip_status, zip_body, _ = http_get(zip_url, timeout=timeout)
    time.sleep(SLEEP_BETWEEN_REQUESTS)
    record: dict[str, Any] = {
        "period": year_month,
        "product": FUNDING_PRODUCT,
        "symbol": FUNDING_SYMBOL,
        "source": "binance_vision_monthly_fundingRate",
        "zip_url": zip_url,
        "checksum_url": checksum_url,
        "retrieval_timestamp_utc": retrieved_at,
        "http_status_zip": zip_status,
        "http_status_checksum": checksum_status,
    }
    if zip_status == 404:
        record["retrieval_status"] = "NOT_FOUND"
        record["container_sha256"] = None
        return record
    if zip_status != 200:
        record["retrieval_status"] = "FETCH_FAILED"
        record["container_sha256"] = None
        return record
    (raw_dir / zip_name).write_bytes(zip_body)
    parsed_checksum = None
    if checksum_status == 200:
        (raw_dir / f"{zip_name}.CHECKSUM").write_bytes(checksum_body)
        parsed_checksum = parse_checksum_text(checksum_body.decode("utf-8"))
        record["expected_sha256"] = parsed_checksum["sha256"]
    record["container_bytes"] = len(zip_body)
    record["container_sha256"] = sha256_of_bytes(zip_body)
    record["checksum_verification"] = evaluate_checksum_verification(
        record["container_sha256"], parsed_checksum, zip_name
    )
    csv_text, members, parser_status = read_zip_csv_member(
        zip_body, funding_csv_member_name(year_month)
    )
    record["archive_members"] = members
    record["member_parser_status"] = parser_status
    if csv_text is None:
        record["retrieval_status"] = "MEMBER_REJECTED"
        record["records"] = []
        return record
    record["member_bytes"] = len(csv_text.encode("utf-8"))
    record["member_sha256"] = sha256_of_bytes(csv_text.encode("utf-8"))
    rows, parse_meta = parse_vision_funding_csv(csv_text)
    record.update(parse_meta)
    record["records"] = rows
    record["audit"] = audit_funding_records(rows)
    record["retrieval_status"] = "ACCEPTED"
    return record


def fetch_rest_funding(*, timeout: float) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    bounds = rest_funding_query_bounds()
    start = bounds["startTime_ms"]
    end_inclusive = bounds["endTime_inclusive_ms"]
    rows: list[dict[str, Any]] = []
    pages = 0
    retrieved_at = _now_utc()
    while True:
        url = (
            f"{FUNDING_REST_ENDPOINT}?symbol={FUNDING_SYMBOL}"
            f"&startTime={start}&endTime={end_inclusive}&limit=1000"
        )
        status, body, _ = http_get(url, timeout=timeout, accept="application/json")
        pages += 1
        time.sleep(0.25)
        if status != 200:
            raise RuntimeError(f"REST fundingRate HTTP {status}: {body[:200]!r}")
        batch = json.loads(body.decode("utf-8"))
        if not isinstance(batch, list):
            raise RuntimeError("REST fundingRate did not return a JSON list")
        if not batch:
            break
        for item in batch:
            time_ms = int(item["fundingTime"])
            if time_ms >= PROTECTED_OOS_START_MS:
                continue
            rows.append(item)
        last = int(batch[-1]["fundingTime"])
        if last <= start or len(batch) < 1000:
            break
        start = last + 1
        if start > end_inclusive:
            break
    provenance = {
        **bounds,
        "retrieval_timestamp_utc": retrieved_at,
        "pages": pages,
        "raw_row_count_including_filtered": len(rows),
        "http_ok": True,
        "user_agent": USER_AGENT,
        "note": (
            "REST-now returning a historical row is not proof of historical "
            "publication latency. STRICT_HISTORICAL_PUBLICATION_LATENCY remains UNPROVEN."
        ),
    }
    return rows, provenance


def _copy_identity_docs(
    *,
    docs_dir: Path,
    snapshot: dict[str, Any],
    object_ledger: dict[str, Any],
    quality: dict[str, Any],
    funding_report: dict[str, Any],
) -> dict[str, str]:
    short = snapshot["snapshot_id"][:8]
    docs_dir.mkdir(parents=True, exist_ok=True)
    snapshot_name = f"SNAPSHOT_{short}.json"
    ledger_name = f"OBJECT_LEDGER_{short}.json"
    quality_name = f"QUALITY_REPORT_{short}.json"
    funding_name = f"FUNDING_COMPATIBILITY_{short}.json"
    write_json(docs_dir / snapshot_name, snapshot)
    write_json(docs_dir / ledger_name, object_ledger)
    write_json(docs_dir / quality_name, quality)
    write_json(docs_dir / funding_name, funding_report)
    hashes = {
        snapshot_name: sha256_of_file(docs_dir / snapshot_name),
        ledger_name: sha256_of_file(docs_dir / ledger_name),
        quality_name: sha256_of_file(docs_dir / quality_name),
        funding_name: sha256_of_file(docs_dir / funding_name),
    }
    return hashes


def run_acquisition(
    *,
    repo_root: Path,
    dataset_root: Path,
    timeout: float,
    emit_docs: bool,
) -> dict[str, Any]:
    assert_no_strategy_quantities(dir())
    git_sha = detect_git_sha(repo_root)
    raw_spot = dataset_root / "raw" / "spot_klines_1h"
    raw_funding = dataset_root / "raw" / "um_fundingRate"
    canonical_dir = dataset_root / "canonical"
    reports_dir = dataset_root / "reports"
    for path in (raw_spot, raw_funding, canonical_dir, reports_dir):
        path.mkdir(parents=True, exist_ok=True)

    spot_months = acquisition_months()
    spot_records = []
    all_rows = []
    source_identities = []
    object_ledger_spot = []
    for month in spot_months:
        print(f"spot {month}", flush=True)
        record = acquire_spot_month(month, raw_spot, timeout=timeout)
        rows = record.pop("rows", [])
        all_rows.extend(rows)
        spot_records.append(record)
        identity = {
            "archive_class": "monthly",
            "archive_object_name": archive_object_name(month),
            "byte_size": record.get("container_bytes"),
            "checksum_verification": record.get("checksum_verification"),
            "expected_sha256": record.get("expected_sha256"),
            "local_sha256": record.get("container_sha256"),
            "member_sha256": record.get("member_sha256"),
            "source_period": month,
            "source_url": record.get("zip_url"),
            "retrieval_timestamp_utc": record.get("retrieval_timestamp_utc"),
            "row_count": record.get("audit", {}).get("row_count"),
            "first_open_time_utc": record.get("audit", {}).get("first_open_time_utc"),
            "last_open_time_utc": record.get("audit", {}).get("last_open_time_utc"),
            "gap_count": record.get("audit", {}).get("missing_count"),
            "duplicate_count": record.get("audit", {}).get("duplicate_count"),
        }
        source_identities.append(identity)
        object_ledger_spot.append({**record, "series": "spot_klines_1h"})

    expected_times = []
    for month in spot_months:
        expected_times.extend(expected_hourly_open_times_ms(month))
    global_audit = audit_spot_rows(all_rows, expected_open_times=expected_times)
    canonical_bytes = canonical_jsonl_bytes(all_rows)
    canonical_path = canonical_dir / "BTCUSDT_SPOT_1h.jsonl"
    canonical_path.write_bytes(canonical_bytes)
    canonical_sha = sha256_of_bytes(canonical_bytes)

    funding_probe_months = iter_year_months("2019-09", ACQUIRE_END_MONTH_INCLUSIVE)
    funding_records = []
    vision_funding_rows = []
    vision_identities = []
    for month in funding_probe_months:
        print(f"funding-vision {month}", flush=True)
        record = acquire_funding_month(month, raw_funding, timeout=timeout)
        rows = record.pop("records", [])
        vision_funding_rows.extend(rows)
        funding_records.append(record)
        if record.get("container_sha256"):
            vision_identities.append(
                {
                    "period": month,
                    "container_sha256": record.get("container_sha256"),
                    "container_bytes": record.get("container_bytes"),
                    "member_sha256": record.get("member_sha256"),
                    "zip_url": record.get("zip_url"),
                    "retrieval_status": record.get("retrieval_status"),
                    "checksum_verification": record.get("checksum_verification"),
                    "row_count": record.get("audit", {}).get("row_count"),
                }
            )

    print("funding-rest", flush=True)
    rest_raw, rest_prov = fetch_rest_funding(timeout=timeout)
    rest_path = canonical_dir / "BTCUSDT_UM_fundingRate_rest_authorized.jsonl"
    rest_lines = [
        json.dumps(
            {
                "fundingRate": item["fundingRate"],
                "fundingTime": int(item["fundingTime"]),
                "markPrice": item.get("markPrice"),
                "symbol": item.get("symbol"),
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        for item in rest_raw
        if int(item["fundingTime"]) < PROTECTED_OOS_START_MS
    ]
    rest_text = ("\n".join(rest_lines) + ("\n" if rest_lines else "")).encode("utf-8")
    rest_path.write_bytes(rest_text)
    rest_sha = sha256_of_bytes(rest_text)
    rest_parsed = parse_rest_funding_records(rest_raw)

    overlap_vision = [
        row for row in vision_funding_rows if row.time_ms >= int(
            datetime(2020, 1, 1, tzinfo=UTC).timestamp() * 1000
        )
    ]
    overlap_rest = [
        row for row in rest_parsed if row.time_ms >= int(
            datetime(2020, 1, 1, tzinfo=UTC).timestamp() * 1000
        )
    ]
    record_compare = compare_funding_records(overlap_rest, overlap_vision)
    rest_pre_vision = [
        row for row in rest_parsed if row.time_ms < int(
            datetime(2020, 1, 1, tzinfo=UTC).timestamp() * 1000
        )
    ]
    b2_06_path = repo_root / B2_06_OBJECT_LEDGER
    b2_06_ledger = json.loads(b2_06_path.read_text(encoding="utf-8"))
    b2_06_hashes = extract_b2_06_funding_container_hashes(b2_06_ledger)
    b2_06_compare_identities = [
        row for row in vision_identities if row["period"] in b2_06_hashes
    ]
    zip_compare = compare_vision_zips_to_b2_06(b2_06_compare_identities, b2_06_hashes)

    construction = construction_code_hashes(repo_root)
    identity_payload = build_spot_identity_payload(
        source_object_identities=source_identities,
        canonical_klines_sha256=canonical_sha,
        canonical_row_count=global_audit["row_count"],
        gap_count=global_audit["missing_count"],
        duplicate_count=global_audit["duplicate_count"],
        construction_code_sha256=construction,
        provenance_git_commit_sha=git_sha,
    )
    snapshot = snapshot_from_payload(identity_payload)
    snapshot_id = snapshot["snapshot_id"]

    quality = {
        "dataset_id": DATASET_ID,
        "duplicate_count": global_audit["duplicate_count"],
        "duplicate_policy": DUPLICATE_POLICY,
        "end_exclusive": END_EXCLUSIVE,
        "expected_native_hours": expected_dataset_hour_count(),
        "first_open_time_utc": global_audit["first_open_time_utc"],
        "gap_count": global_audit["missing_count"],
        "gap_policy": GAP_POLICY,
        "gap_ranges": global_audit["missing_open_time_ranges_ms"],
        "headline_timerange_start_utc": "2019-10-01T00:00:00Z",
        "invariant_violation_count": global_audit["invariant_violation_count"],
        "is_strictly_ordered_by_open_time": global_audit["is_strictly_ordered_by_open_time"],
        "kline_mapping": kline_mapping_record(),
        "last_open_time_utc": global_audit["last_open_time_utc"],
        "malformed_source_rows": sum(r.get("malformed_row_count") or 0 for r in spot_records),
        "market_03_scientifically_bound": False,
        "market_type": MARKET_TYPE,
        "native_interval": INTERVAL,
        "normalization_rules": list(NORMALIZATION_RULES),
        "protected_oos_used_for_science": False,
        "row_count": global_audit["row_count"],
        "schema_ok": global_audit["schema_ok"],
        "snapshot_id": snapshot_id,
        "source_months_accepted": sum(
            1 for r in spot_records if r.get("retrieval_status", "").startswith("ACCEPTED")
        ),
        "source_months_expected": len(spot_months),
        "start_inclusive": START_INCLUSIVE,
        "startup_candle_count_external": STARTUP_CANDLE_COUNT,
        "symbol": SYMBOL,
        "warmup_open_time_utc": iso_utc_from_ms(warmup_open_time_ms()),
        "zero_volume_count": global_audit["zero_volume_count"],
        "canonical_klines_sha256": canonical_sha,
        "canonical_bytes": len(canonical_bytes),
    }

    vision_not_found = [
        r["period"] for r in funding_records if r.get("retrieval_status") == "NOT_FOUND"
    ]
    funding_report = {
        "b2_06_dataset_id": B2_06_DATASET_ID,
        "b2_06_snapshot_id": B2_06_SNAPSHOT_ID,
        "b2_06_execution_authorized": False,
        "b2_06_research_authorized": False,
        "external_source_endpoint": FUNDING_REST_PATH,
        "external_source_field": "fundingRate",
        "external_source_timestamp": "fundingTime",
        "external_product": FUNDING_PRODUCT,
        "external_symbol": FUNDING_SYMBOL,
        "vision_product": FUNDING_PRODUCT,
        "vision_series": "monthly/fundingRate/BTCUSDT",
        "vision_field": "last_funding_rate",
        "vision_timestamp": "calc_time",
        "vision_start_month_present": FUNDING_VISION_START_MONTH,
        "vision_months_not_found": vision_not_found,
        "rest_provenance": {**rest_prov, "sha256": rest_sha, "bytes": len(rest_text)},
        "rest_integrity": audit_funding_records(rest_parsed),
        "vision_integrity": audit_funding_records(vision_funding_rows),
        "rest_pre_vision_2019": {
            "row_count": len(rest_pre_vision),
            "first_time_utc": (
                iso_utc_from_ms(rest_pre_vision[0].time_ms) if rest_pre_vision else None
            ),
            "last_time_utc": (
                iso_utc_from_ms(rest_pre_vision[-1].time_ms) if rest_pre_vision else None
            ),
        },
        "record_level_semantic_equivalence_authorized_overlap": record_compare,
        "vision_vs_b2_06_container_identity": zip_compare,
        "same_economic_series_class": True,
        "same_frozen_object_as_rest": False,
        "b2_06_semantically_equivalent_on_overlapping_vision_bytes": zip_compare[
            "all_overlapping_containers_byte_identical"
        ],
        "strict_historical_publication_latency": STRICT_HISTORICAL_PUBLICATION_LATENCY,
        "reproduction_fundingtime_assumption_meaning": (
            REPRODUCTION_FUNDINGTIME_ASSUMPTION_MEANING
        ),
        "does_not_solve_b2_06_publication_blocker": True,
        "protected_oos_compared": False,
        "strategy_outcomes_compared": False,
    }

    object_ledger = {
        "dataset_id": DATASET_ID,
        "snapshot_id": snapshot_id,
        "spot_objects": object_ledger_spot,
        "funding_vision_objects": funding_records,
        "duplicate_policy": DUPLICATE_POLICY,
        "gap_policy": GAP_POLICY,
    }
    write_json(reports_dir / "snapshot_manifest.json", snapshot)
    write_json(reports_dir / "object_ledger.json", object_ledger)
    write_json(reports_dir / "quality_report.json", quality)
    write_json(reports_dir / "funding_compatibility.json", funding_report)

    docs_hashes = {}
    if emit_docs:
        docs_dir = repo_root / "docs" / "research_data" / DATASET_ID
        docs_hashes = _copy_identity_docs(
            docs_dir=docs_dir,
            snapshot=snapshot,
            object_ledger=object_ledger,
            quality=quality,
            funding_report=funding_report,
        )

    result = {
        "dataset_id": DATASET_ID,
        "snapshot_id": snapshot_id,
        "spot_time_bounds": {
            "start_inclusive": START_INCLUSIVE,
            "end_exclusive": END_EXCLUSIVE,
            "first_open_time_utc": global_audit["first_open_time_utc"],
            "last_open_time_utc": global_audit["last_open_time_utc"],
        },
        "spot_rows": global_audit["row_count"],
        "spot_gaps": global_audit["missing_count"],
        "spot_duplicates": global_audit["duplicate_count"],
        "spot_data_sha256": canonical_sha,
        "quality": quality,
        "funding": funding_report,
        "docs_hashes": docs_hashes,
        "freqtrade_first_open_date": (
            freqtrade_date_from_open_time_ms(all_rows[0].open_time_ms) if all_rows else None
        ),
        "MARKET_03_STRATEGY_EXECUTED": False,
        "MARKET_03_OUTCOMES_INSPECTED": False,
        "MARKET_03_PARAMETER_SEARCH": False,
        "MARKET_03_PREREGISTERED": False,
        "MARKET_03_ARMED": False,
        "PROTECTED_OOS_USED_FOR_SCIENCE": False,
    }
    write_json(reports_dir / "acquisition_result.json", result)
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path("/workspace"))
    parser.add_argument(
        "--dataset-root",
        type=Path,
        default=Path("/workspace/artifacts/research_data") / DATASET_ID,
    )
    parser.add_argument("--timeout-seconds", type=float, default=DEFAULT_TIMEOUT)
    parser.add_argument("--allow-acquire", action="store_true")
    parser.add_argument("--emit-docs", action="store_true")
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    if not args.allow_acquire:
        print("refusing acquisition without --allow-acquire", file=sys.stderr)
        return 2
    result = run_acquisition(
        repo_root=args.repo_root.resolve(),
        dataset_root=args.dataset_root.resolve(),
        timeout=args.timeout_seconds,
        emit_docs=args.emit_docs,
    )
    print(dumps_deterministic({
        "dataset_id": result["dataset_id"],
        "snapshot_id": result["snapshot_id"],
        "spot_rows": result["spot_rows"],
        "spot_gaps": result["spot_gaps"],
        "spot_duplicates": result["spot_duplicates"],
        "spot_data_sha256": result["spot_data_sha256"],
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
