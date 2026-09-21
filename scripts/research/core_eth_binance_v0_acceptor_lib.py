"""Outcome-blind CORE_ETH_BINANCE_V0 companion acceptor.

Downloads and verifies the frozen Vision ETHUSDT 1m inventory, audits
timestamp/schema/coverage identity, and constructs an immutable snapshot.

This module does not compute MARKET-05 outcomes, ETH/BTC predictive
relationships, Y, MAE, coefficients, or fold predictions. Price values
are used only for 12-column schema / OHLC invariant checks and are not
retained in the snapshot identity payload.
"""

from __future__ import annotations

import hashlib
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterable, Optional
from urllib.request import Request, urlopen

from scripts.research.core_btc_binance_v0_probe_lib import (
    BAR_MS,
    audit_klines_window,
    day_bounds_ms,
    evaluate_checksum_verification,
    month_bounds_ms,
    parse_checksum_text,
    parse_kline_csv,
    read_kline_csv_member_named,
    sha256_of_bytes,
    sha256_of_file,
)

UTC = timezone.utc

DATASET_ID = "CORE_ETH_BINANCE_V0"
COMPANION_OF = "CORE_BTC_BINANCE_V0"
INSTRUMENT = "ETHUSDT"
INTERVAL = "1m"
INVENTORY_REL = "docs/research_data/CORE_ETH_BINANCE_V0/SOURCE_INVENTORY.json"
INVENTORY_SHA256 = "033a06428d5d2a56fcde23a8fe64ebe4d8afa2f57d5d3263e3d0b9c6db38e49e"
MANIFEST_REL = "docs/manifests/CORE_ETH_BINANCE_V0.yaml"
BTC_SNAPSHOT_ID = "717d37a404f81eefd58c9a796cc11868c48226baf1de8ffecad5e5607f8dd415"
EXPECTED_OBJECTS = 104
EXPECTED_1M_ROWS = 3_497_760
START_INCLUSIVE = "2020-01-01T00:00:00Z"
END_EXCLUSIVE = "2026-08-26T00:00:00Z"
START_MS = int(datetime(2020, 1, 1, tzinfo=UTC).timestamp() * 1000)
END_MS = int(datetime(2026, 8, 26, tzinfo=UTC).timestamp() * 1000)
DEVELOPMENT_END_MS = int(datetime(2025, 1, 1, tzinfo=UTC).timestamp() * 1000)
DEVELOPMENT_EXPECTED_1M_ROWS = (DEVELOPMENT_END_MS - START_MS) // BAR_MS


class CoreEthBinanceV0AcceptorError(RuntimeError):
    """Fail-closed ETH companion identity / coverage error."""


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_json_bytes(payload: dict) -> bytes:
    return (
        json.dumps(
            payload,
            sort_keys=True,
            indent=2,
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def load_bound_inventory(repo_root: Optional[Path] = None) -> dict:
    root = repo_root or _repo_root()
    path = root / INVENTORY_REL
    digest = sha256_file(path)
    if digest != INVENTORY_SHA256:
        raise CoreEthBinanceV0AcceptorError(
            f"CORE_ETH_INVENTORY_SHA256_MISMATCH:{digest}"
        )
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("dataset_id") != DATASET_ID:
        raise CoreEthBinanceV0AcceptorError("CORE_ETH_INVENTORY_DATASET_MISMATCH")
    if payload.get("instrument") != INSTRUMENT:
        raise CoreEthBinanceV0AcceptorError("CORE_ETH_INVENTORY_INSTRUMENT_MISMATCH")
    if payload.get("companion_of") != COMPANION_OF:
        raise CoreEthBinanceV0AcceptorError("CORE_ETH_INVENTORY_COMPANION_MISMATCH")
    if payload.get("does_not_redefine_core_btc_binance_v0") is not True:
        raise CoreEthBinanceV0AcceptorError("CORE_ETH_REDEFINES_BTC")
    records = payload.get("checksum_records") or []
    if len(records) != EXPECTED_OBJECTS:
        raise CoreEthBinanceV0AcceptorError("CORE_ETH_INVENTORY_OBJECT_COUNT_MISMATCH")
    return payload


def zip_url_from_checksum_url(checksum_url: str) -> str:
    if not checksum_url.endswith(".CHECKSUM"):
        raise CoreEthBinanceV0AcceptorError("CORE_ETH_CHECKSUM_URL_SHAPE")
    return checksum_url[: -len(".CHECKSUM")]


def expected_csv_member(archive_class: str, source_period: str) -> str:
    return f"{INSTRUMENT}-{INTERVAL}-{source_period}.csv"


def window_bounds_ms(archive_class: str, source_period: str) -> tuple[int, int]:
    if archive_class == "monthly":
        return month_bounds_ms(source_period)
    if archive_class == "daily":
        return day_bounds_ms(source_period)
    raise CoreEthBinanceV0AcceptorError(f"CORE_ETH_UNKNOWN_ARCHIVE_CLASS:{archive_class}")


def default_fetch(url: str, timeout_seconds: float = 120.0) -> bytes:
    req = Request(
        url,
        headers={"User-Agent": "signalbot-core-eth-acceptor/1.0"},
    )
    with urlopen(req, timeout=timeout_seconds) as resp:
        status = getattr(resp, "status", 200)
        if status not in (200, None):
            raise CoreEthBinanceV0AcceptorError(f"CORE_ETH_HTTP_{status}:{url}")
        return resp.read()


def acquire_verified_zip(
    record: dict,
    dest_dir: Path,
    *,
    fetch: Callable[[str], bytes] = default_fetch,
) -> dict:
    zip_name = record["expected_zip_filename"]
    expected_sha = str(record["checksum_sha256"]).lower()
    zip_path = dest_dir / zip_name
    checksum_path = dest_dir / f"{zip_name}.CHECKSUM"
    dest_dir.mkdir(parents=True, exist_ok=True)
    checksum_url = record["checksum_url"]
    zip_url = zip_url_from_checksum_url(checksum_url)
    if zip_path.exists():
        local_sha = sha256_of_file(zip_path)
        if local_sha != expected_sha:
            raise CoreEthBinanceV0AcceptorError(
                f"CORE_ETH_REVISION_CONFLICT:{zip_name}"
            )
        zip_bytes = zip_path.read_bytes()
        disposition = "REUSED_IDENTICAL"
    else:
        zip_bytes = fetch(zip_url)
        local_sha = sha256_of_bytes(zip_bytes)
        if local_sha != expected_sha:
            raise CoreEthBinanceV0AcceptorError(
                f"CORE_ETH_ZIP_CHECKSUM_MISMATCH:{zip_name}"
            )
        zip_path.write_bytes(zip_bytes)
        disposition = "NEW"
    checksum_bytes = fetch(checksum_url) if not checksum_path.exists() else checksum_path.read_bytes()
    if not checksum_path.exists():
        checksum_path.write_bytes(checksum_bytes)
    parsed = parse_checksum_text(checksum_bytes.decode("utf-8"))
    verification = evaluate_checksum_verification(local_sha, parsed, zip_name)
    if verification != "VERIFIED":
        raise CoreEthBinanceV0AcceptorError(
            f"CORE_ETH_CHECKSUM_NOT_VERIFIED:{zip_name}:{verification}"
        )
    if parsed["sha256"] != expected_sha:
        raise CoreEthBinanceV0AcceptorError(
            f"CORE_ETH_INVENTORY_CHECKSUM_DRIFT:{zip_name}"
        )
    return {
        "zip_path": str(zip_path),
        "zip_sha256": local_sha,
        "disposition": disposition,
        "checksum_verification": verification,
        "byte_size": len(zip_bytes),
    }


def audit_object_timestamps(
    zip_path: Path,
    record: dict,
) -> dict:
    """Schema + timestamp audit. Does not retain OHLC values."""
    member = expected_csv_member(record["archive_class"], record["source_period"])
    text, names, status = read_kline_csv_member_named(zip_path, member)
    if status != "OK" or text is None:
        raise CoreEthBinanceV0AcceptorError(
            f"CORE_ETH_CSV_MEMBER_FAIL:{record['expected_zip_filename']}:{status}:{names}"
        )
    rows, parse_meta = parse_kline_csv(text)
    start_ms, end_ms = window_bounds_ms(record["archive_class"], record["source_period"])
    audit = audit_klines_window(
        rows, start_ms, end_ms, int(parse_meta["malformed_row_count"])
    )
    open_times = [int(row.open_time_ms) for row in rows]
    if len(open_times) != len(set(open_times)):
        raise CoreEthBinanceV0AcceptorError(
            f"CORE_ETH_DUPLICATE_OPEN_TIME:{record['source_period']}"
        )
    if open_times != sorted(open_times):
        raise CoreEthBinanceV0AcceptorError(
            f"CORE_ETH_OPEN_TIME_NOT_SORTED:{record['source_period']}"
        )
    return {
        "source_period": record["source_period"],
        "archive_class": record["archive_class"],
        "parser_status": status,
        "malformed_row_count": int(parse_meta["malformed_row_count"]),
        "invariant_violation_count": int(audit["invariant_violation_count"]),
        "duplicate_count": int(audit["duplicate_count"]),
        "missing_bucket_count": int(audit["missing_bucket_count"]),
        "observed_rows": int(audit["observed_rows"]),
        "expected_rows": int(audit["expected_rows"]),
        "first_open_time_ms": open_times[0] if open_times else None,
        "last_open_time_ms": open_times[-1] if open_times else None,
        "open_times_ms": open_times,
    }


def _fail_if_object_unclean(audit: dict) -> None:
    if audit["malformed_row_count"] != 0:
        raise CoreEthBinanceV0AcceptorError(
            f"CORE_ETH_MALFORMED:{audit['source_period']}"
        )
    if audit["invariant_violation_count"] != 0:
        raise CoreEthBinanceV0AcceptorError(
            f"CORE_ETH_INVARIANT:{audit['source_period']}"
        )
    if audit["duplicate_count"] != 0:
        raise CoreEthBinanceV0AcceptorError(
            f"CORE_ETH_DUPLICATES:{audit['source_period']}"
        )
    if audit["missing_bucket_count"] != 0:
        raise CoreEthBinanceV0AcceptorError(
            f"CORE_ETH_MISSING_MINUTES:{audit['source_period']}"
        )
    if audit["observed_rows"] != audit["expected_rows"]:
        raise CoreEthBinanceV0AcceptorError(
            f"CORE_ETH_ROW_COUNT:{audit['source_period']}"
        )


def merge_open_times(object_audits: Iterable[dict]) -> list[int]:
    merged: list[int] = []
    seen: set[int] = set()
    for audit in object_audits:
        for ts in audit["open_times_ms"]:
            if ts in seen:
                raise CoreEthBinanceV0AcceptorError(
                    f"CORE_ETH_CROSS_OBJECT_DUPLICATE:{ts}"
                )
            seen.add(ts)
            merged.append(ts)
    merged.sort()
    return merged


def continuity_from_open_times(open_times: list[int]) -> dict:
    expected = list(range(START_MS, END_MS, BAR_MS))
    observed = set(open_times)
    missing = [ts for ts in expected if ts not in observed]
    extra = [ts for ts in open_times if ts < START_MS or ts >= END_MS]
    development_expected = list(range(START_MS, DEVELOPMENT_END_MS, BAR_MS))
    development_missing = [ts for ts in development_expected if ts not in observed]
    if extra:
        raise CoreEthBinanceV0AcceptorError("CORE_ETH_EXTRA_OUT_OF_RANGE_BARS")
    return {
        "expected_1m_rows": len(expected),
        "accepted_1m_rows": len(open_times),
        "missing_1m_rows": len(missing),
        "development_expected_1m_rows": len(development_expected),
        "development_missing_1m_rows": len(development_missing),
        "first_open_time_ms": open_times[0] if open_times else None,
        "last_open_time_ms": open_times[-1] if open_times else None,
        "first_open_time_utc": datetime.fromtimestamp(open_times[0] / 1000, tz=UTC).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        if open_times
        else None,
        "last_open_time_utc": datetime.fromtimestamp(open_times[-1] / 1000, tz=UTC).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        if open_times
        else None,
    }


def snapshot_identity_payload(
    *,
    object_records: list[dict],
    continuity: dict,
    inventory_sha256: str,
) -> dict:
    return {
        "schema": "core_eth_binance_v0_snapshot_identity",
        "schema_version": "1.0.0",
        "dataset_id": DATASET_ID,
        "companion_of": COMPANION_OF,
        "does_not_redefine_core_btc_binance_v0": True,
        "instrument": INSTRUMENT,
        "market_type": "USD_M_FUTURES",
        "provider": "Binance",
        "native_interval": INTERVAL,
        "bar_availability": "bar_end_exclusive",
        "available_at": "open_time + 60s",
        "start_inclusive": START_INCLUSIVE,
        "end_exclusive": END_EXCLUSIVE,
        "source_inventory_sha256": inventory_sha256,
        "source_object_count": EXPECTED_OBJECTS,
        "source_checksum_verified_count": EXPECTED_OBJECTS,
        "expected_1m_rows": continuity["expected_1m_rows"],
        "accepted_1m_rows": continuity["accepted_1m_rows"],
        "missing_1m_rows": continuity["missing_1m_rows"],
        "duplicate_1m_rows": 0,
        "malformed_rows": 0,
        "invariant_violation_rows": 0,
        "development_expected_1m_rows": continuity["development_expected_1m_rows"],
        "development_missing_1m_rows": continuity["development_missing_1m_rows"],
        "first_open_time_utc": continuity["first_open_time_utc"],
        "last_open_time_utc": continuity["last_open_time_utc"],
        "btc_companion_snapshot_id": BTC_SNAPSHOT_ID,
        "scientific_outcomes_inspected": False,
        "protected_oos_scientific_values_inspected": False,
        "price_values_retained_in_snapshot": False,
        "objects": object_records,
    }


def snapshot_id_from_payload(payload: dict) -> str:
    return hashlib.sha256(canonical_json_bytes(payload)).hexdigest()


def accept_core_eth(
    *,
    raw_root: Path,
    repo_root: Optional[Path] = None,
    fetch: Callable[[str], bytes] = default_fetch,
) -> dict:
    """Acquire, verify, audit timestamps, and accept CORE_ETH_BINANCE_V0."""
    root = repo_root or _repo_root()
    inventory = load_bound_inventory(root)
    records = inventory["checksum_records"]
    acquired_by_period: dict[str, dict] = {}

    def _acquire(record: dict) -> tuple[str, dict]:
        return record["source_period"], acquire_verified_zip(record, raw_root, fetch=fetch)

    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = [pool.submit(_acquire, record) for record in records]
        for fut in as_completed(futures):
            period, acquired = fut.result()
            acquired_by_period[period] = acquired

    object_audits = []
    object_identity = []
    for record in records:
        acquired = acquired_by_period[record["source_period"]]
        audit = audit_object_timestamps(Path(acquired["zip_path"]), record)
        _fail_if_object_unclean(audit)
        object_audits.append(audit)
        object_identity.append(
            {
                "source_period": record["source_period"],
                "archive_class": record["archive_class"],
                "expected_zip_filename": record["expected_zip_filename"],
                "zip_sha256": acquired["zip_sha256"],
                "byte_size": acquired["byte_size"],
                "observed_rows": audit["observed_rows"],
                "first_open_time_ms": audit["first_open_time_ms"],
                "last_open_time_ms": audit["last_open_time_ms"],
            }
        )
    open_times = merge_open_times(object_audits)
    continuity = continuity_from_open_times(open_times)
    if continuity["expected_1m_rows"] != EXPECTED_1M_ROWS:
        raise CoreEthBinanceV0AcceptorError("CORE_ETH_EXPECTED_ROW_CONTRACT_MISMATCH")
    if continuity["missing_1m_rows"] != 0:
        raise CoreEthBinanceV0AcceptorError("CORE_ETH_FULL_RANGE_INCOMPLETE")
    if continuity["development_missing_1m_rows"] != 0:
        raise CoreEthBinanceV0AcceptorError("CORE_ETH_DEVELOPMENT_WINDOW_INCOMPLETE")
    if continuity["accepted_1m_rows"] != EXPECTED_1M_ROWS:
        raise CoreEthBinanceV0AcceptorError("CORE_ETH_ACCEPTED_ROW_MISMATCH")
    if continuity["first_open_time_utc"] != START_INCLUSIVE:
        raise CoreEthBinanceV0AcceptorError("CORE_ETH_FIRST_OPEN_MISMATCH")
    if continuity["last_open_time_utc"] != "2026-08-25T23:59:00Z":
        raise CoreEthBinanceV0AcceptorError("CORE_ETH_LAST_OPEN_MISMATCH")
    payload = snapshot_identity_payload(
        object_records=object_identity,
        continuity=continuity,
        inventory_sha256=INVENTORY_SHA256,
    )
    snap_id = snapshot_id_from_payload(payload)
    payload["snapshot_id"] = snap_id
    return {
        "dataset_id": DATASET_ID,
        "snapshot_id": snap_id,
        "accepted": True,
        "identity_payload": payload,
        "continuity": continuity,
        "scientific_outcomes_inspected": False,
        "protected_oos_scientific_values_inspected": False,
    }


def manifest_yaml(snapshot_id: str, payload: dict) -> str:
    return f"""dataset_id: CORE_ETH_BINANCE_V0
manifest_version: 0
status: ACCEPTED_FOR_DISCOVERY
current_state: ACCEPTED_FOR_DISCOVERY
research_authorized: true
confirmatory_authorized: false
accepted_for_discovery: true
created_at_utc: '2026-09-19T00:00:00Z'
accepted_on_utc: '2026-09-19'
contract_path: docs/CORE_BTC_BINANCE_V0_CONTRACT.md
companion_of: CORE_BTC_BINANCE_V0
does_not_redefine_core_btc_binance_v0: true
source_inventory_path: docs/research_data/CORE_ETH_BINANCE_V0/SOURCE_INVENTORY.json
source_inventory_sha256: {INVENTORY_SHA256}
snapshot_id: {snapshot_id}
bound_by_unit: MARKET_05_CROSS_ASSET_IMPLEMENTATION
btc_companion_snapshot_id: {BTC_SNAPSHOT_ID}

purpose:
  class: CORE_LONG_HISTORY_COMPANION
  description: >-
    ETH companion to CORE_BTC_BINANCE_V0 for MARKET-05 cross-asset
    confirmation research. Same exchange, same instrument class, same
    frozen range, same bar-end-exclusive availability. Accepted for
    discovery identity only. This is not a MARKET-05 RESULT and does
    not authorize scientific execution.
  not_an_edge_claim: true
  not_a_market_05_result: true

source:
  provider: Binance
  evidence_tier: OFFICIAL_ARCHIVE
  archive_root: https://data.binance.vision/data/futures/um
  market_type: USD_M_FUTURES
  instrument: ETHUSDT
  data_type: klines
  native_interval: 1m
  documented_api_origin: /fapi/v1/klines

frozen_target_range:
  start_inclusive: '2020-01-01T00:00:00Z'
  end_exclusive: '2026-08-26T00:00:00Z'
  timezone: UTC
  matches_core_btc_binance_v0: true
  observed_first_open_time: '{payload["first_open_time_utc"]}'
  observed_last_open_time: '{payload["last_open_time_utc"]}'

availability_semantics:
  source_bar_duration_seconds: 60
  canonical_available_at: bar_end_exclusive
  eligibility_rule: bar_end_exclusive <= decision_time
  close_time_is_not_available_at: true
  archive_is_live_equivalent: false
  evidence_semantics: HISTORICAL_COMPARABLE

acquisition_policy:
  completed_months_prefer_monthly_archive: true
  incomplete_month_use_daily_archive: true
  intended_initial_monthly_range:
    start_month: '2020-01'
    end_month: '2026-07'
  intended_initial_daily_range:
    start_date: '2026-08-01'
    end_date: '2026-08-25'
  require_source_checksum: true
  overwrite_frozen_raw_files: false

object_inventory:
  expected_objects: 104
  listed_zip_objects: 104
  listed_checksum_objects: 104
  missing_zip_objects: 0
  missing_checksum_objects: 0
  checksum_filename_mismatches: 0
  full_continuity_audit_complete: true
  accepted_1m_rows: {payload["accepted_1m_rows"]}
  expected_1m_rows_if_complete: 3497760
  missing_1m_rows: {payload["missing_1m_rows"]}
  duplicate_1m_rows: 0

acceptance_meaning:
  ACCEPTED_FOR_DISCOVERY: >-
    The snapshot is authorized as the ETH companion identity for
    MARKET-05 implementation. It does not authorize ARM, scientific
    execution, outcome inspection, or confirmatory research.

excluded_sources_and_features:
  - open_interest
  - funding
  - liquidations
  - order_book
  - spot_market
  - bybit
  - okx
  - btc_binance_plus_eth_other_exchange
  - btc_perp_plus_eth_spot
  - silent_redefinition_of_CORE_BTC_BINANCE_V0

notes:
  - >-
    This identity exists so MARKET-05 can name a same-exchange ETH
    companion without mutating CORE_BTC_BINANCE_V0.
  - >-
    Snapshot identity hashes verified ZIP bytes plus timestamp coverage.
    Price values are not retained in the snapshot payload.
  - >-
    Protected 2025/2026 timestamps were audited for coverage/order/duplicates
    only. Scientific OHLC evaluation of those values was not performed.
  - >-
    2026-08 monthly ZIP exists on Vision but is outside the CORE cutoff
    and is not adopted.
"""
