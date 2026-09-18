"""MARKET-03 dedicated Binance USD-M BTCUSDT REST funding snapshot helpers.

Outcome-blind. Does not compute 3-day means, 180-day percentiles,
funding_pct, EMA, entries, exits, trades, or any performance quantity.

Wraps the already-acquired REST JSONL whose identity is frozen in the
MARKET-03 acquisition/prereg records. Does not treat B2-06 as authority.
"""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional, Sequence

UTC = timezone.utc

DATASET_ID = "MARKET_03_BINANCE_UM_BTCUSDT_FUNDINGRATE_REST_V0"
PROVIDER = "Binance"
VENUE = "Binance"
MARKET_TYPE = "USD_M_PERPETUAL"
SYMBOL = "BTCUSDT"
ENDPOINT_PATH = "/fapi/v1/fundingRate"
PRIMARY_ENDPOINT = "https://fapi.binance.com/fapi/v1/fundingRate"
ENDPOINT_USED = "https://www.binance.com/fapi/v1/fundingRate"
SCHEMA_FIELDS = ("fundingRate", "fundingTime", "symbol")

EXPECTED_SOURCE_SHA256 = (
    "e7885cd53407d70b4627d58b9abf2cdf5b26cdc7097a139eac2e454ad75944cb"
)
EXPECTED_SOURCE_SIZE = 442988
EXPECTED_ROW_COUNT = 5819
EXPECTED_FIRST_FUNDINGTIME_UTC = "2019-09-10T08:00:00Z"
EXPECTED_LAST_FUNDINGTIME_UTC = "2024-12-31T16:00:00Z"

SOURCE_RELATIVE_PATH = (
    "artifacts/research_data/MARKET_03_BINANCE_SPOT_BTCUSDT_1H_V0/"
    "canonical/BTCUSDT_UM_fundingRate_rest_authorized.jsonl"
)
ACQUISITION_COMPATIBILITY_RELATIVE_PATH = (
    "docs/research_data/MARKET_03_BINANCE_SPOT_BTCUSDT_1H_V0/"
    "FUNDING_COMPATIBILITY_2ce1f504.json"
)

SPOT_DATASET_ID = "MARKET_03_BINANCE_SPOT_BTCUSDT_1H_V0"
SPOT_SNAPSHOT_ID = "2ce1f504709dc40c37a70dddcf73acb444e715820e9c855f6817c48f10d2b345"
SPOT_DATA_SHA256 = "e560bebb6ba9d070ee0fa58aaa5cf922caaa24d4b7e2b4eac8c7c0041c9495d4"

PREREG_MD_SHA256 = (
    "044bb2a6bbd51c49c856b02eb7866b43171664a05d947dce995489389eeb0b57"
)
PREREG_JSON_SHA256 = (
    "3f35f9a1d0575eaff3a1993a4779642259c0891dbdda1d49f22b958eba714f89"
)

B2_06_DATASET_ID = "B2_06_BINANCE_UM_BTCUSDT_OI_FUNDING_V0"
B2_06_SNAPSHOT_ID = "5a9d036b23721d75b519b8478b81e333791227376d25cbeea5f0666c90730a33"

PROTECTED_OOS_START_MS = int(datetime(2025, 1, 1, tzinfo=UTC).timestamp() * 1000)
END_EXCLUSIVE = "2025-01-01T00:00:00Z"
EVALUATION_START_UTC = "2019-10-01T00:00:00Z"
EVALUATION_START_MS = int(datetime(2019, 10, 1, tzinfo=UTC).timestamp() * 1000)
REQUEST_START_INCLUSIVE = "2019-09-01T00:00:00Z"
REQUEST_START_MS = 1567296000000
REQUEST_END_EXCLUSIVE_MS = PROTECTED_OOS_START_MS
RETRIEVAL_TIMESTAMP_UTC = "2026-09-18T17:06:53Z"

EIGHT_HOURS_MS = 8 * 3600 * 1000
HOUR_MS = 3600 * 1000
EXPECTED_UTC_HOURS = (0, 8, 16)

STRICT_HISTORICAL_PUBLICATION_LATENCY = "UNPROVEN"
REPRODUCTION_FUNDINGTIME_ASSUMPTION = "ACCEPTABLE"
REPRODUCTION_FUNDINGTIME_ASSUMPTION_MEANING = (
    "A funding observation is treated as historically available at its "
    "Binance fundingTime because that matches the pinned external "
    "EmaCrossFunding implementation. This LEVEL_2 reproduction assumption "
    "is ACCEPTABLE. It does not prove publication latency, does not set "
    "legal_available_at, and does not solve the B2-06 publication-timing "
    "blocker."
)

PRE_SNAPSHOT_HEAD = "3f1722476927a13d4e1629510f12ed00f72ba3d8"
PRE_SNAPSHOT_TREE = "50f2d54fe4ddfc7a6774808cc7110913ea0b978b"

CONSTRUCTION_CODE_PATHS = (
    "scripts/research/market_03_binance_um_btcusdt_fundingrate_rest_v0_lib.py",
    "scripts/research/market_03_binance_um_btcusdt_fundingrate_rest_v0_materialize.py",
)

NORMALIZATION_RULES = (
    "identity_copy_of_acquired_rest_jsonl",
    "preserve_fundingRate_decimal_string",
    "preserve_fundingTime_int_ms",
    "preserve_symbol",
    "no_rounding",
    "no_forward_fill",
    "no_resample",
    "no_strategy_transform",
    "no_b2_06_substitution",
    "drop_protected_oos_if_present_fail_closed",
)

DUPLICATE_POLICY = "ENUMERATE_DO_NOT_KEEP_FIRST_OR_LAST_OR_REPAIR"
GAP_POLICY = "ENUMERATE_MISSING_8H_HOUR_FLOOR_EVENTS_DO_NOT_SYNTHESIZE"
MS_RESIDUAL_POLICY = "PRESERVE_RAW_FUNDINGTIME_DO_NOT_ROUND_TO_HOUR"

FORBIDDEN_STRATEGY_TOKENS = (
    "ema600",
    "funding_pct",
    "funding_3d",
    "equity_curve",
    "cagr",
    "sharpe",
    "sortino",
    "drawdown",
    "pnl",
)


class Market03FundingSnapshotError(ValueError):
    """Fail-closed MARKET-03 funding snapshot construction error."""


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


def iso_utc_from_ms(time_ms: int) -> str:
    return (
        datetime.fromtimestamp(time_ms / 1000.0, tz=UTC)
        .isoformat(timespec="milliseconds" if time_ms % 1000 else "seconds")
        .replace("+00:00", "Z")
        .replace(".000Z", "Z")
    )


def hour_floor_ms(time_ms: int) -> int:
    return (time_ms // HOUR_MS) * HOUR_MS


def construction_code_hashes(repo_root: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for rel in CONSTRUCTION_CODE_PATHS:
        path = repo_root / rel
        if not path.is_file():
            raise Market03FundingSnapshotError(f"missing construction file {rel}")
        out[rel] = sha256_of_file(path)
    return out


def assert_no_strategy_quantities(namespace: Iterable[str]) -> None:
    lowered = {name.lower() for name in namespace}
    for token in FORBIDDEN_STRATEGY_TOKENS:
        if token in lowered:
            raise Market03FundingSnapshotError(
                f"forbidden MARKET-03 strategy quantity present: {token}"
            )


def _finite_decimal(value: str, field: str) -> Decimal:
    parsed = Decimal(value)
    if not parsed.is_finite():
        raise InvalidOperation(f"non-finite {field}")
    return parsed


@dataclass(frozen=True)
class FundingSourceRow:
    funding_time_ms: int
    funding_rate: str
    symbol: str
    extra_fields: tuple[tuple[str, Any], ...]
    source_line: str

    def canonical_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "fundingRate": self.funding_rate,
            "fundingTime": self.funding_time_ms,
            "symbol": self.symbol,
        }
        for key, value in self.extra_fields:
            payload[key] = value
        return payload


def parse_rest_funding_jsonl(text: str) -> list[FundingSourceRow]:
    rows: list[FundingSourceRow] = []
    for line_no, raw_line in enumerate(text.splitlines(), start=1):
        if not raw_line:
            continue
        try:
            obj = json.loads(raw_line)
        except json.JSONDecodeError as exc:
            raise Market03FundingSnapshotError(
                f"malformed JSONL at line {line_no}: {exc}"
            ) from exc
        if not isinstance(obj, dict):
            raise Market03FundingSnapshotError(
                f"JSONL line {line_no} is not an object"
            )
        missing = [field for field in SCHEMA_FIELDS if field not in obj]
        if missing:
            raise Market03FundingSnapshotError(
                f"JSONL line {line_no} missing fields {missing}"
            )
        try:
            time_ms = int(obj["fundingTime"])
        except (TypeError, ValueError) as exc:
            raise Market03FundingSnapshotError(
                f"JSONL line {line_no} invalid fundingTime"
            ) from exc
        if time_ms >= PROTECTED_OOS_START_MS:
            raise Market03FundingSnapshotError(
                "protected OOS fundingTime present; refuse silently dropping"
            )
        if time_ms < 0:
            raise Market03FundingSnapshotError(
                f"JSONL line {line_no} negative fundingTime"
            )
        rate = obj["fundingRate"]
        if not isinstance(rate, str):
            raise Market03FundingSnapshotError(
                f"JSONL line {line_no} fundingRate is not a decimal string"
            )
        try:
            _finite_decimal(rate, "fundingRate")
        except InvalidOperation as exc:
            raise Market03FundingSnapshotError(
                f"JSONL line {line_no} non-finite fundingRate"
            ) from exc
        symbol = obj["symbol"]
        if symbol != SYMBOL:
            raise Market03FundingSnapshotError(
                f"JSONL line {line_no} unexpected symbol {symbol!r}"
            )
        extra = tuple(
            (key, obj[key])
            for key in sorted(obj)
            if key not in SCHEMA_FIELDS
        )
        rows.append(
            FundingSourceRow(
                funding_time_ms=time_ms,
                funding_rate=rate,
                symbol=str(symbol),
                extra_fields=extra,
                source_line=raw_line,
            )
        )
    return rows


def canonical_jsonl_bytes(rows: Sequence[FundingSourceRow]) -> bytes:
    lines = [
        json.dumps(row.canonical_dict(), sort_keys=True, separators=(",", ":"))
        for row in rows
    ]
    return ("\n".join(lines) + ("\n" if lines else "")).encode("utf-8")


def prove_source_fidelity(
    rows: Sequence[FundingSourceRow],
    canonical_bytes: bytes,
) -> dict[str, Any]:
    canonical_lines = [
        line for line in canonical_bytes.decode("utf-8").splitlines() if line
    ]
    if len(canonical_lines) != len(rows):
        raise Market03FundingSnapshotError(
            "canonical row count drifted from source parse"
        )
    string_equal = 0
    decimal_equal = 0
    time_equal = 0
    mismatches: list[dict[str, Any]] = []
    for index, (row, line) in enumerate(zip(rows, canonical_lines)):
        obj = json.loads(line)
        time_ok = int(obj["fundingTime"]) == row.funding_time_ms
        rate_string_ok = obj["fundingRate"] == row.funding_rate
        try:
            rate_decimal_ok = Decimal(obj["fundingRate"]) == Decimal(row.funding_rate)
        except InvalidOperation:
            rate_decimal_ok = False
        if time_ok:
            time_equal += 1
        if rate_string_ok:
            string_equal += 1
        if rate_decimal_ok:
            decimal_equal += 1
        if not (time_ok and rate_string_ok and rate_decimal_ok):
            if len(mismatches) < 10:
                mismatches.append(
                    {
                        "index": index,
                        "source_fundingTime": row.funding_time_ms,
                        "canonical_fundingTime": obj.get("fundingTime"),
                        "source_fundingRate": row.funding_rate,
                        "canonical_fundingRate": obj.get("fundingRate"),
                    }
                )
    if mismatches:
        raise Market03FundingSnapshotError(
            "normalization altered scientifically relevant funding values"
        )
    line_byte_identical = 0
    for row, line in zip(rows, canonical_lines):
        if row.source_line == line:
            line_byte_identical += 1
    return {
        "row_count": len(rows),
        "fundingTime_identical_count": time_equal,
        "fundingRate_string_identical_count": string_equal,
        "fundingRate_decimal_identical_count": decimal_equal,
        "source_line_byte_identical_count": line_byte_identical,
        "mismatch_count": 0,
        "mismatches": [],
        "scientifically_relevant_values_unaltered": True,
    }


def audit_funding_rows(rows: Sequence[FundingSourceRow]) -> dict[str, Any]:
    times = [row.funding_time_ms for row in rows]
    time_counts = Counter(times)
    duplicate_times = sorted(ts for ts, count in time_counts.items() if count > 1)
    exact_line_counts = Counter(row.source_line for row in rows)
    exact_duplicate_lines = sorted(
        line for line, count in exact_line_counts.items() if count > 1
    )
    rates_by_time: dict[int, set[str]] = {}
    for row in rows:
        rates_by_time.setdefault(row.funding_time_ms, set()).add(row.funding_rate)
    conflicting = sorted(
        ts for ts, rates in rates_by_time.items() if len(rates) > 1
    )
    non_finite = 0
    for row in rows:
        try:
            if not Decimal(row.funding_rate).is_finite():
                non_finite += 1
        except InvalidOperation:
            non_finite += 1
    monotonic = (
        all(times[i] < times[i + 1] for i in range(len(times) - 1))
        if len(times) > 1
        else True
    )
    ordered_non_decreasing = (
        all(times[i] <= times[i + 1] for i in range(len(times) - 1))
        if len(times) > 1
        else True
    )
    hour_floors = [hour_floor_ms(ts) for ts in times]
    unique_hour_floors = sorted(set(hour_floors))
    missing_hour_floors: list[int] = []
    extra_hour_floors: list[int] = []
    expected_hour_floors: list[int] = []
    if unique_hour_floors:
        cursor = unique_hour_floors[0]
        last = unique_hour_floors[-1]
        while cursor <= last:
            expected_hour_floors.append(cursor)
            cursor += EIGHT_HOURS_MS
        missing_hour_floors = sorted(set(expected_hour_floors) - set(unique_hour_floors))
        extra_hour_floors = sorted(set(unique_hour_floors) - set(expected_hour_floors))
    interval_counts = Counter(
        times[i + 1] - times[i] for i in range(len(times) - 1)
    )
    residuals = [ts - hour_floor_ms(ts) for ts in times]
    nonzero_residuals = [value for value in residuals if value]
    utc_hours = [
        datetime.fromtimestamp(hour / 1000.0, tz=UTC).hour
        for hour in unique_hour_floors
    ]
    unexpected_hours = sorted(
        {hour for hour in utc_hours if hour not in EXPECTED_UTC_HOURS}
    )
    anomalies: list[dict[str, Any]] = []
    if duplicate_times:
        anomalies.append(
            {
                "class": "DUPLICATE_FUNDINGTIME",
                "count": len(duplicate_times),
                "head_ms": duplicate_times[:20],
                "repaired": False,
            }
        )
    if exact_duplicate_lines:
        anomalies.append(
            {
                "class": "EXACT_DUPLICATE_ROWS",
                "count": len(exact_duplicate_lines),
                "repaired": False,
            }
        )
    if conflicting:
        anomalies.append(
            {
                "class": "CONFLICTING_DUPLICATE_FUNDINGTIME",
                "count": len(conflicting),
                "head_ms": conflicting[:20],
                "repaired": False,
            }
        )
    if missing_hour_floors:
        anomalies.append(
            {
                "class": "MISSING_EXPECTED_8H_HOUR_FLOOR_EVENT",
                "count": len(missing_hour_floors),
                "head_utc": [iso_utc_from_ms(ts) for ts in missing_hour_floors[:20]],
                "repaired": False,
            }
        )
    if extra_hour_floors:
        anomalies.append(
            {
                "class": "UNEXPECTED_HOUR_FLOOR_EVENT",
                "count": len(extra_hour_floors),
                "head_utc": [iso_utc_from_ms(ts) for ts in extra_hour_floors[:20]],
                "repaired": False,
            }
        )
    if unexpected_hours:
        anomalies.append(
            {
                "class": "FUNDING_HOUR_NOT_00_08_16_UTC",
                "hours": unexpected_hours,
                "repaired": False,
            }
        )
    if nonzero_residuals:
        anomalies.append(
            {
                "class": "FUNDINGTIME_MILLISECOND_RESIDUAL",
                "count": len(nonzero_residuals),
                "min_ms": min(nonzero_residuals),
                "max_ms": max(nonzero_residuals),
                "policy": MS_RESIDUAL_POLICY,
                "repaired": False,
                "note": (
                    "Raw fundingTime milliseconds after the UTC hour are "
                    "preserved. They are not rounded and are not treated as "
                    "proven publication latency."
                ),
            }
        )
    first_ms = times[0] if times else None
    last_ms = times[-1] if times else None
    rows_before_eval = sum(1 for ts in times if ts < EVALUATION_START_MS)
    return {
        "row_count": len(rows),
        "schema_ok": True,
        "symbol_identity_ok": all(row.symbol == SYMBOL for row in rows),
        "finite_fundingRate_count": len(rows) - non_finite,
        "non_finite_rate_count": non_finite,
        "valid_fundingTime_count": len(rows),
        "chronological_strictly_increasing": monotonic,
        "chronological_non_decreasing": ordered_non_decreasing,
        "duplicate_fundingTime_count": len(duplicate_times),
        "duplicate_fundingTime_ms": duplicate_times[:50],
        "exact_duplicate_row_count": len(exact_duplicate_lines),
        "conflicting_duplicate_fundingTime_count": len(conflicting),
        "conflicting_duplicate_fundingTime_ms": conflicting[:50],
        "first_fundingTime_ms": first_ms,
        "last_fundingTime_ms": last_ms,
        "first_fundingTime_utc": iso_utc_from_ms(first_ms) if first_ms is not None else None,
        "last_fundingTime_utc": iso_utc_from_ms(last_ms) if last_ms is not None else None,
        "protected_oos_row_count": 0,
        "rows_before_evaluation_start": rows_before_eval,
        "rows_on_or_after_evaluation_start": len(rows) - rows_before_eval,
        "hours_from_first_observation_to_evaluation_start": (
            (EVALUATION_START_MS - first_ms) / HOUR_MS if first_ms is not None else None
        ),
        "eight_hour_hour_floor_expected_count": len(expected_hour_floors),
        "eight_hour_hour_floor_observed_count": len(unique_hour_floors),
        "missing_expected_8h_hour_floor_count": len(missing_hour_floors),
        "unexpected_hour_floor_count": len(extra_hour_floors),
        "missing_expected_8h_hour_floor_utc_head": [
            iso_utc_from_ms(ts) for ts in missing_hour_floors[:20]
        ],
        "interval_unique_count": len(interval_counts),
        "interval_distribution_head": [
            {"delta_ms": delta, "count": count}
            for delta, count in interval_counts.most_common(12)
        ],
        "exact_8h_adjacent_count": interval_counts.get(EIGHT_HOURS_MS, 0),
        "nonzero_hour_residual_count": len(nonzero_residuals),
        "hour_residual_min_ms": min(nonzero_residuals) if nonzero_residuals else 0,
        "hour_residual_max_ms": max(nonzero_residuals) if nonzero_residuals else 0,
        "utc_hour_counts": {
            str(hour): utc_hours.count(hour) for hour in sorted(set(utc_hours))
        },
        "anomalies": anomalies,
        "anomalies_repaired": False,
        "duplicate_policy": DUPLICATE_POLICY,
        "gap_policy": GAP_POLICY,
        "ms_residual_policy": MS_RESIDUAL_POLICY,
    }


def load_acquisition_rest_provenance(repo_root: Path) -> dict[str, Any]:
    path = repo_root / ACQUISITION_COMPATIBILITY_RELATIVE_PATH
    payload = json.loads(path.read_text(encoding="utf-8"))
    rest = payload["rest_provenance"]
    if rest["sha256"] != EXPECTED_SOURCE_SHA256:
        raise Market03FundingSnapshotError(
            "acquisition rest_provenance.sha256 drifted from frozen identity"
        )
    if rest["bytes"] != EXPECTED_SOURCE_SIZE:
        raise Market03FundingSnapshotError(
            "acquisition rest_provenance.bytes drifted from frozen identity"
        )
    if rest["path"] != ENDPOINT_PATH:
        raise Market03FundingSnapshotError("acquisition endpoint path mismatch")
    if rest["symbol"] != SYMBOL:
        raise Market03FundingSnapshotError("acquisition symbol mismatch")
    return rest


def verify_source_file(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise Market03FundingSnapshotError(
            f"funding REST JSONL not found at {path}"
        )
    size = path.stat().st_size
    digest = sha256_of_file(path)
    if size != EXPECTED_SOURCE_SIZE:
        raise Market03FundingSnapshotError(
            f"source size {size} != expected {EXPECTED_SOURCE_SIZE}"
        )
    if digest != EXPECTED_SOURCE_SHA256:
        raise Market03FundingSnapshotError(
            "source SHA256 does not match frozen MARKET-03 REST identity "
            f"{EXPECTED_SOURCE_SHA256}"
        )
    return {
        "path": str(path),
        "sha256": digest,
        "size": size,
    }


def build_funding_identity_payload(
    *,
    canonical_funding_sha256: str,
    canonical_row_count: int,
    first_fundingTime_utc: str,
    last_fundingTime_utc: str,
    duplicate_fundingTime_count: int,
    missing_expected_8h_count: int,
    construction_code_sha256: Mapping[str, str],
    source_sha256: str,
    source_size: int,
    source_relative_path: str,
    rest_provenance: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "b2_06_dataset_id_not_authority": B2_06_DATASET_ID,
        "b2_06_is_not_market_03_authority": True,
        "b2_06_snapshot_id_not_authority": B2_06_SNAPSHOT_ID,
        "canonical_funding_sha256": canonical_funding_sha256,
        "canonical_row_count": canonical_row_count,
        "construction_code_sha256": dict(construction_code_sha256),
        "dataset_id": DATASET_ID,
        "duplicate_fundingTime_count": duplicate_fundingTime_count,
        "duplicate_policy": DUPLICATE_POLICY,
        "end_exclusive": END_EXCLUSIVE,
        "endpoint_path": ENDPOINT_PATH,
        "endpoint_used": ENDPOINT_USED,
        "evaluation_start_utc": EVALUATION_START_UTC,
        "exchange": VENUE,
        "first_fundingTime_utc": first_fundingTime_utc,
        "gap_policy": GAP_POLICY,
        "last_fundingTime_utc": last_fundingTime_utc,
        "market_03_arm_bound": False,
        "market_03_scientifically_bound": False,
        "market_type": MARKET_TYPE,
        "missing_expected_8h_hour_floor_count": missing_expected_8h_count,
        "ms_residual_policy": MS_RESIDUAL_POLICY,
        "normalization_rules": list(NORMALIZATION_RULES),
        "primary_endpoint": PRIMARY_ENDPOINT,
        "protected_oos_excluded": True,
        "provenance_git_commit_sha": PRE_SNAPSHOT_HEAD,
        "provenance_git_tree_sha": PRE_SNAPSHOT_TREE,
        "provider": PROVIDER,
        "reproduction_fundingtime_assumption": REPRODUCTION_FUNDINGTIME_ASSUMPTION,
        "request_end_exclusive_ms": rest_provenance.get(
            "endTime_exclusive_ms", REQUEST_END_EXCLUSIVE_MS
        ),
        "request_start_ms": rest_provenance.get("startTime_ms", REQUEST_START_MS),
        "retrieval_timestamp_utc": rest_provenance.get(
            "retrieval_timestamp_utc", RETRIEVAL_TIMESTAMP_UTC
        ),
        "schema": list(SCHEMA_FIELDS),
        "source_relative_path": source_relative_path,
        "source_sha256": source_sha256,
        "source_size_bytes": source_size,
        "strict_historical_publication_latency": (
            STRICT_HISTORICAL_PUBLICATION_LATENCY
        ),
        "symbol": SYMBOL,
    }


def snapshot_from_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    snapshot_id = sha256_of_canonical_identity_payload(payload)
    return {"identity_payload": payload, "snapshot_id": snapshot_id}


def refuse_b2_06_as_authority(claimed: Optional[str]) -> None:
    if claimed in {B2_06_DATASET_ID, B2_06_SNAPSHOT_ID}:
        raise Market03FundingSnapshotError(
            "B2-06 is not MARKET-03 funding authority"
        )
