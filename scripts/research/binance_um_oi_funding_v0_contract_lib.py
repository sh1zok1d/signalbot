"""Outcome-blind B2-06 OI + funding data-expansion contract.

This module freezes first-party Binance USD-M BTCUSDT open-interest and
settled-funding identity, decision-time availability, missing-vs-corrupt
classification, same-support eligibility, and Git-bound snapshot identity.

It does not:

- execute B2-06 science, crowding thresholds, or promotion metrics;
- authorize CORE / 2025 / 2026 outcome access;
- download or inspect live Binance history (callers may supply bytes);
- extend ``CORE_BTC_BINANCE_V0``, which remains kline-only;
- treat ``available_at`` as optional, caller-selected, or equal to retrieval
  time.

Network access is intentionally absent. Tests and later materializers inject
local bytes.
"""
from __future__ import annotations

import calendar
import hashlib
import io
import json
import re
import zipfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import yaml

from scripts.research.lib.research_harness import (
    CodeIdentityError,
    DatasetIdentityError,
    VerifiedCodeFreeze,
    read_frozen_git_bytes,
    verify_git_freeze,
)

UTC = timezone.utc

DATASET_ID = "B2_06_BINANCE_UM_BTCUSDT_OI_FUNDING_V0"
CONTRACT_PATH = "docs/research/B2_06_LEVERAGE_CROWDING_DATA_EXPANSION.md"
FREEZE_JSON_PATH = "docs/research/B2_06_LEVERAGE_CROWDING_DATA_EXPANSION.json"
MANIFEST_PATH = "docs/manifests/B2_06_BINANCE_UM_BTCUSDT_OI_FUNDING_V0.yaml"
NORMALIZATION_MODULE = "scripts/research/binance_um_oi_funding_v0_contract_lib.py"

SCHEMA_VERSION = "v1"
AVAILABILITY_SEMANTICS_VERSION = "v2-oi-bar-end-exclusive-funding-publication-unproven"
NORMALIZATION_VERSION = "v1"
RETRIEVAL_METHOD_VERSION = "binance-vision-official-archive-sha256sum-v1"
SNAPSHOT_IDENTITY_VERSION = "v2-exact-git-object-authority"
CONTRACT_STATUS = "CONTRACT_FROZEN_NOT_MATERIALIZED"
UNIT_VERDICT = (
    "DATA_CONTRACT_FROZEN_AWAITING_MATERIALIZATION_AND_FUNDING_AVAILABILITY_AUTHORITY"
)
FUNDING_PUBLICATION_SEMANTICS_STATUS = "FUNDING_PUBLICATION_LATENCY_UNPROVEN"
FUNDING_PUBLICATION_PROVEN_STATUS = "PROVEN_FIRST_PARTY_PUBLICATION"
OI_DUPLICATE_EQUALITY_RULE = "ENTIRE_FROZEN_RAW_ROW"

PROVIDER = "Binance"
VENUE = "Binance"
MARKET_TYPE = "USD_M_FUTURES"
CONTRACT_TYPE = "PERPETUAL"
SYMBOL = "BTCUSDT"
TIMEZONE_NAME = "UTC"

ARCHIVE_ROOT = "https://data.binance.vision/data/futures/um"
FUNDING_SERIES_PREFIX = "monthly/fundingRate/BTCUSDT"
OI_SERIES_PREFIX = "daily/metrics/BTCUSDT"
FUNDING_OBJECT_TEMPLATE = "BTCUSDT-fundingRate-{year:04d}-{month:02d}.zip"
OI_OBJECT_TEMPLATE = "BTCUSDT-metrics-{year:04d}-{month:02d}-{day:02d}.zip"
FUNDING_CSV_MEMBER_TEMPLATE = "BTCUSDT-fundingRate-{year:04d}-{month:02d}.csv"
OI_CSV_MEMBER_TEMPLATE = "BTCUSDT-metrics-{year:04d}-{month:02d}-{day:02d}.csv"

FUNDING_HEADER = ("calc_time", "funding_interval_hours", "last_funding_rate")
OI_HEADER = (
    "create_time",
    "symbol",
    "sum_open_interest",
    "sum_open_interest_value",
    "count_toptrader_long_short_ratio",
    "sum_toptrader_long_short_ratio",
    "count_long_short_ratio",
    "sum_taker_long_short_vol_ratio",
)

OI_DEFINITION = "SUM_OPEN_INTEREST_USD_M_BTCUSDT"
OI_UNITS = "BTC"
OI_NATIVE_GRANULARITY = "5m"
OI_PERIOD_MS = 5 * 60 * 1000
OI_CREATE_TIME_FORMAT = "%Y-%m-%d %H:%M:%S"

FUNDING_DEFINITION = "SETTLED_LAST_FUNDING_RATE"
FUNDING_INTERVAL_HOURS = 8
FUNDING_PERIOD_MS = FUNDING_INTERVAL_HOURS * 60 * 60 * 1000
FUNDING_SETTLEMENT_SNAP_TOLERANCE_MS = 1000

OI_MAX_STALENESS_MS = OI_PERIOD_MS
FUNDING_MAX_STALENESS_MS = FUNDING_PERIOD_MS

# Joint B2-06 crowding inputs cannot exist before first-party OI archive
# objects. Funding monthly files exist from 2020-01; they do not fill OI.
JOINT_DEVELOPMENT_START_INCLUSIVE = "2020-09-01T00:00:00Z"
# Exclusive of 2025: this unit does not open validation/OOS years.
JOINT_DEVELOPMENT_END_EXCLUSIVE = "2025-01-01T00:00:00Z"
FUNDING_ARCHIVE_DEV_START = "2020-01"
OI_ARCHIVE_DEV_START = "2020-09-01"

FORBIDDEN_FUNDING_DEFINITIONS = frozenset(
    {
        "PREDICTED_NEXT_FUNDING_RATE",
        "PREMIUM_INDEX_IMPLIED",
        "MARK_INDEX_PREMIUM",
        "ANNOUNCED_UNSETTLED",
        "REALIZED_PAYMENT_NOTIONAL",
    }
)
FORBIDDEN_OI_DEFINITIONS = frozenset(
    {
        "SUM_OPEN_INTEREST_VALUE_USDT",
        "COIN_M_CONTRACTS",
        "SPOT_BORROW",
        "VENDOR_NORMALIZED_OI",
    }
)
FORBIDDEN_PROVIDERS = frozenset({"Bybit", "OKX", "Tardis", "HuggingFace", "SignalbotLive"})
FORBIDDEN_VENUES = frozenset({"Bybit", "OKX"})
FORBIDDEN_MARKET_TYPES = frozenset({"COIN_M_FUTURES", "SPOT", "OPTIONS"})
FORBIDDEN_CONTRACT_TYPES = frozenset({"DELIVERY", "QUARTERLY", "INVERSE_PERPETUAL"})
FORBIDDEN_TIMEFRAMES = frozenset({"1m", "1s", "15m", "1h", "1d"})
FORBIDDEN_DATASET_IDS = frozenset({"CORE_BTC_BINANCE_V0"})

SNAPSHOT_AUTHORITY_KIND = "EXACT_GIT_COMMIT_TREE_OBJECT_AUTHORITY"
MANIFEST_BINDING = (
    "exact Git commit/tree blob at docs/manifests/B2_06_BINANCE_UM_BTCUSDT_OI_FUNDING_V0.yaml"
)
_OI_FUNDING_GIT_TOKEN = object()
ZIP_MATERIALIZER_FAIL_CLOSED = (
    "unexpected member filename",
    "multiple CSV members",
    "duplicate member names",
    "extra hidden CSV members",
    "path traversal",
    "absolute paths",
    "malformed UTF-8",
    "unsupported compression/container shape",
)

_SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")
_YEAR_MONTH_RE = re.compile(r"^(\d{4})-(\d{2})$")
_YEAR_MONTH_DAY_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")
_UTF8_BOM = "\ufeff"


class OiFundingContractError(ValueError):
    """Base class for the B2-06 data-expansion contract."""


class OiFundingCorruptError(OiFundingContractError):
    """Input is malformed, conflicting, or integrity-invalid. Not missing."""


class OiFundingMissingError(OiFundingContractError):
    """Genuinely unavailable / not-yet-mature / cadence hole."""


class OiFundingIdentityError(OiFundingContractError):
    """Wrong venue/symbol/contract/source/dataset identity."""


class OiFundingLookaheadError(OiFundingContractError):
    """Observation is not legally usable at decision time T."""


class OiFundingSupportError(OiFundingContractError):
    """Candidate/baseline support is not identical."""


class OiFundingAuthorizationError(OiFundingContractError):
    """Outcome access or caller-selected authority is forbidden."""


FROZEN_SOURCE = {
    "provider": PROVIDER,
    "venue": VENUE,
    "market_type": MARKET_TYPE,
    "contract_type": CONTRACT_TYPE,
    "symbol": SYMBOL,
    "oi_series": OI_SERIES_PREFIX,
    "funding_series": FUNDING_SERIES_PREFIX,
    "oi_definition": OI_DEFINITION,
    "oi_units": OI_UNITS,
    "oi_native_granularity": OI_NATIVE_GRANULARITY,
    "funding_definition": FUNDING_DEFINITION,
    "funding_interval_hours": FUNDING_INTERVAL_HOURS,
    "timezone": TIMEZONE_NAME,
    "dataset_id": DATASET_ID,
}


def dumps_deterministic(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_text(text: str) -> str:
    return sha256_hex(text.encode("utf-8"))


def sha256_of_canonical_identity_payload(payload: Mapping[str, Any]) -> str:
    return sha256_text(dumps_deterministic(dict(payload)))


def parse_checksum_text(text: str) -> dict[str, str]:
    stripped = text.strip()
    if not stripped:
        raise OiFundingCorruptError("empty checksum file")
    parts = stripped.split(None, 1)
    digest = parts[0].strip()
    if not _SHA256_RE.fullmatch(digest):
        raise OiFundingCorruptError(
            f"checksum file's first token is not a 64-hex sha256: {digest!r}"
        )
    filename = parts[1].strip() if len(parts) > 1 else ""
    if filename.startswith("*"):
        filename = filename[1:]
    if not filename:
        raise OiFundingCorruptError("checksum file missing object filename")
    return {"sha256": digest.lower(), "filename": filename}


def verify_source_checksum(
    *,
    zip_bytes: bytes,
    checksum_text: str,
    expected_zip_filename: str,
) -> str:
    parsed = parse_checksum_text(checksum_text)
    actual = sha256_hex(zip_bytes)
    if parsed["filename"] != expected_zip_filename:
        raise OiFundingCorruptError(
            "checksum filename identity mismatch: "
            f"{parsed['filename']!r} != {expected_zip_filename!r}"
        )
    if actual != parsed["sha256"]:
        raise OiFundingCorruptError(
            f"checksum mismatch: local {actual} != sidecar {parsed['sha256']}"
        )
    return "VERIFIED"


def require_frozen_source(identity: Mapping[str, Any]) -> None:
    if not isinstance(identity, Mapping):
        raise OiFundingIdentityError("source identity must be a mapping")
    for key, expected in FROZEN_SOURCE.items():
        got = identity.get(key)
        if got != expected:
            raise OiFundingIdentityError(
                f"source identity field {key} must be {expected!r}, got {got!r}"
            )
    extra_provider = identity.get("alternate_provider")
    extra_venue = identity.get("fallback_venue")
    extra_timeframe = identity.get("fallback_timeframe")
    extra_dataset = identity.get("dataset_id_override")
    if extra_provider:
        raise OiFundingIdentityError("alternate_provider is forbidden")
    if extra_venue:
        raise OiFundingIdentityError("fallback_venue is forbidden")
    if extra_timeframe:
        raise OiFundingIdentityError("fallback_timeframe is forbidden")
    if extra_dataset:
        raise OiFundingIdentityError("dataset_id_override is forbidden")


def select_source(requested: Mapping[str, Any]) -> dict[str, Any]:
    """Runtime callers may not choose an alternate OI/funding source."""
    if requested.get("dataset_id") in FORBIDDEN_DATASET_IDS:
        raise OiFundingIdentityError(
            "CORE_BTC_BINANCE_V0 is kline-only and cannot supply OI/funding"
        )
    require_frozen_source(requested)
    if requested.get("provider") in FORBIDDEN_PROVIDERS:
        raise OiFundingIdentityError("forbidden provider")
    return dict(FROZEN_SOURCE)


def _reject_forbidden_identity(
    *,
    provider: str,
    venue: str,
    market_type: str,
    contract_type: str,
    symbol: str,
    oi_definition: str | None = None,
    oi_units: str | None = None,
    oi_granularity: str | None = None,
    funding_definition: str | None = None,
) -> None:
    if provider != PROVIDER:
        raise OiFundingIdentityError(f"wrong provider: {provider!r}")
    if venue != VENUE:
        raise OiFundingIdentityError(f"wrong venue: {venue!r}")
    if market_type != MARKET_TYPE:
        raise OiFundingIdentityError(f"wrong market type: {market_type!r}")
    if contract_type != CONTRACT_TYPE:
        raise OiFundingIdentityError(f"wrong contract type: {contract_type!r}")
    if symbol != SYMBOL:
        raise OiFundingIdentityError(f"wrong symbol: {symbol!r}")
    if provider in FORBIDDEN_PROVIDERS or venue in FORBIDDEN_VENUES:
        raise OiFundingIdentityError("cross-provider/venue fallback is forbidden")
    if market_type in FORBIDDEN_MARKET_TYPES:
        raise OiFundingIdentityError("forbidden market type")
    if contract_type in FORBIDDEN_CONTRACT_TYPES:
        raise OiFundingIdentityError("forbidden contract type")
    if oi_definition is not None:
        if oi_definition != OI_DEFINITION or oi_definition in FORBIDDEN_OI_DEFINITIONS:
            raise OiFundingIdentityError(f"wrong OI definition: {oi_definition!r}")
    if oi_units is not None and oi_units != OI_UNITS:
        raise OiFundingIdentityError(f"wrong OI units: {oi_units!r}")
    if oi_granularity is not None:
        if oi_granularity != OI_NATIVE_GRANULARITY or oi_granularity in FORBIDDEN_TIMEFRAMES:
            raise OiFundingIdentityError(
                f"wrong OI granularity/timeframe: {oi_granularity!r}"
            )
    if funding_definition is not None:
        if (
            funding_definition != FUNDING_DEFINITION
            or funding_definition in FORBIDDEN_FUNDING_DEFINITIONS
        ):
            raise OiFundingIdentityError(
                f"wrong funding definition: {funding_definition!r}"
            )


def split_csv_rows(text: str) -> tuple[tuple[str, ...], list[list[str]]]:
    if text.startswith(_UTF8_BOM):
        text = text[len(_UTF8_BOM):]
    if not text.strip():
        raise OiFundingCorruptError("empty CSV")
    lines = text.splitlines()
    header = tuple(part.strip() for part in lines[0].split(","))
    body: list[list[str]] = []
    for line in lines[1:]:
        if not line.strip():
            continue
        body.append([part.strip() for part in line.split(",")])
    return header, body


def _require_header(header: Sequence[str], expected: Sequence[str], kind: str) -> None:
    if tuple(header) != tuple(expected):
        raise OiFundingCorruptError(
            f"{kind} schema mismatch: {tuple(header)!r} != {tuple(expected)!r}"
        )


def _finite_decimal(raw: str, *, field: str) -> Decimal:
    try:
        value = Decimal(raw)
    except (InvalidOperation, ValueError) as exc:
        raise OiFundingCorruptError(f"non-decimal {field}: {raw!r}") from exc
    if not value.is_finite():
        raise OiFundingCorruptError(f"non-finite {field}: {raw!r}")
    return value


def _parse_int_ms(raw: str, *, field: str) -> int:
    if not re.fullmatch(r"-?\d+", raw):
        raise OiFundingCorruptError(f"malformed timestamp {field}: {raw!r}")
    try:
        value = int(raw)
    except ValueError as exc:
        raise OiFundingCorruptError(f"malformed timestamp {field}: {raw!r}") from exc
    if value < 0:
        raise OiFundingCorruptError(f"impossible timestamp {field}: {value}")
    return value


def nearest_8h_settlement_ms(calc_time_ms: int) -> int:
    if FUNDING_PERIOD_MS <= 0:
        raise OiFundingCorruptError("funding period must be positive")
    quarter = (calc_time_ms + FUNDING_PERIOD_MS // 2) // FUNDING_PERIOD_MS
    return int(quarter * FUNDING_PERIOD_MS)


def funding_legal_available_at_ms(_calc_time_ms: int) -> int:
    """Fail closed: archive calc_time is not a proven publication clock.

    First-party Vision files do not establish zero publication latency.
    Inventing +1s/+1m/+5m would be unscientific. Legal consumption is blocked
    until a later materialization unit freezes a first-party publication rule.
    """
    raise OiFundingLookaheadError(
        "FUNDING_PUBLICATION_LATENCY_UNPROVEN: calc_time is not a proven "
        "legal_available_at and must not authorize research use"
    )


def oi_available_at_ms(period_start_ms: int) -> int:
    """Vision ``create_time`` matches 5m bucket-start labels.

    Conservative CORE-consistent rule: the snapshot is not legally usable
    until the 5-minute window has closed. This refuses lookahead if the
    label is a period start. It delays a true point-in-time snapshot by at
    most one native interval.
    """
    return period_start_ms + OI_PERIOD_MS


def parse_oi_create_time_ms(raw: str) -> int:
    try:
        dt = datetime.strptime(raw, OI_CREATE_TIME_FORMAT).replace(tzinfo=UTC)
    except ValueError as exc:
        raise OiFundingCorruptError(f"malformed timestamp create_time: {raw!r}") from exc
    return int(dt.timestamp() * 1000)


def assert_no_lookahead(*, decision_t_ms: int, available_at_ms: int) -> None:
    if available_at_ms is None:
        raise OiFundingLookaheadError("missing availability metadata")
    if int(available_at_ms) > int(decision_t_ms):
        raise OiFundingLookaheadError(
            f"available_at {available_at_ms} is after decision T {decision_t_ms}"
        )


def require_availability_metadata(record: Mapping[str, Any]) -> int:
    if "available_at_ms" not in record or record.get("available_at_ms") is None:
        raise OiFundingLookaheadError("missing availability metadata")
    try:
        return int(record["available_at_ms"])
    except (TypeError, ValueError) as exc:
        raise OiFundingCorruptError("malformed available_at_ms") from exc


def observation_usable_at(*, record: Mapping[str, Any], decision_t_ms: int) -> bool:
    status = record.get("publication_semantics_status")
    if status == FUNDING_PUBLICATION_SEMANTICS_STATUS or (
        record.get("funding_definition") == FUNDING_DEFINITION
        and status != FUNDING_PUBLICATION_PROVEN_STATUS
    ):
        raise OiFundingLookaheadError(
            "FUNDING_PUBLICATION_LATENCY_UNPROVEN: archived settled funding "
            "cannot be used at T merely because calc_time <= T"
        )
    if record.get("legal_available_at_ms") is None and record.get(
        "funding_definition"
    ) == FUNDING_DEFINITION:
        raise OiFundingLookaheadError(
            "FUNDING_PUBLICATION_LATENCY_UNPROVEN: legal_available_at is not established"
        )
    available_at = require_availability_metadata(record)
    published = record.get("published_at_ms")
    if published is not None:
        try:
            published_ms = int(published)
        except (TypeError, ValueError) as exc:
            raise OiFundingCorruptError("malformed published_at_ms") from exc
        legal = max(available_at, published_ms)
    else:
        legal = available_at
    retrieval = record.get("retrieval_time_ms")
    if retrieval is not None:
        try:
            int(retrieval)
        except (TypeError, ValueError) as exc:
            raise OiFundingCorruptError("malformed retrieval_time_ms") from exc
    return legal <= int(decision_t_ms)


def assert_funding_legally_consumable(
    row: "NormalizedFundingRow",
    decision_t_ms: int,
) -> None:
    if row.publication_semantics_status != FUNDING_PUBLICATION_PROVEN_STATUS:
        raise OiFundingLookaheadError(
            "FUNDING_PUBLICATION_LATENCY_UNPROVEN: calc_time is not legal_available_at"
        )
    if row.legal_available_at_ms is None:
        raise OiFundingLookaheadError(
            "FUNDING_PUBLICATION_LATENCY_UNPROVEN: legal_available_at is not established"
        )
    observation_usable_at(
        record={
            "available_at_ms": row.legal_available_at_ms,
            "publication_semantics_status": row.publication_semantics_status,
            "funding_definition": row.funding_definition,
            "legal_available_at_ms": row.legal_available_at_ms,
        },
        decision_t_ms=decision_t_ms,
    )


@dataclass(frozen=True)
class NormalizedFundingRow:
    provider: str
    venue: str
    market_type: str
    contract_type: str
    symbol: str
    source_event_time_ms: int
    period_start_ms: int
    period_end_ms: int
    canonical_settlement_ms: int
    publication_semantics_status: str
    legal_available_at_ms: int | None
    funding_interval_hours: int
    last_funding_rate: str
    funding_definition: str
    archive_object_name: str


@dataclass(frozen=True)
class NormalizedOiRow:
    provider: str
    venue: str
    market_type: str
    contract_type: str
    symbol: str
    source_event_time_ms: int
    period_start_ms: int
    period_end_ms: int
    published_at_ms: int
    available_at_ms: int
    sum_open_interest: str
    oi_definition: str
    oi_units: str
    oi_native_granularity: str
    identical_duplicate_collapsed: bool
    archive_object_name: str
    duplicate_equality_rule: str


def parse_funding_archive_year_month(archive_object_name: str) -> str:
    match = re.fullmatch(r"BTCUSDT-fundingRate-(\d{4}-\d{2})\.zip", archive_object_name)
    if not match:
        raise OiFundingCorruptError(
            f"funding archive object identity mismatch: {archive_object_name!r}"
        )
    year_month = match.group(1)
    funding_object_name(year_month)
    return year_month


def parse_oi_archive_day(archive_object_name: str) -> str:
    match = re.fullmatch(r"BTCUSDT-metrics-(\d{4}-\d{2}-\d{2})\.zip", archive_object_name)
    if not match:
        raise OiFundingCorruptError(
            f"OI archive object identity mismatch: {archive_object_name!r}"
        )
    day = match.group(1)
    oi_object_name(day)
    return day


def _utc_year_month(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000, tz=UTC).strftime("%Y-%m")


def _utc_day(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000, tz=UTC).strftime("%Y-%m-%d")


def normalize_funding_rows(
    csv_text: str,
    *,
    identity: Mapping[str, Any],
    archive_object_name: str,
    published_at_by_event_ms: Mapping[int, int] | None = None,
) -> list[NormalizedFundingRow]:
    require_frozen_source(identity)
    if published_at_by_event_ms:
        raise OiFundingAuthorizationError(
            "caller-supplied funding published_at is not first-party publication authority"
        )
    requested_month = parse_funding_archive_year_month(archive_object_name)
    header, body = split_csv_rows(csv_text)
    _require_header(header, FUNDING_HEADER, "funding")
    if identity.get("funding_definition") in FORBIDDEN_FUNDING_DEFINITIONS:
        raise OiFundingIdentityError("wrong funding definition")

    by_event: dict[int, tuple[NormalizedFundingRow, tuple[str, ...]]] = {}
    for raw in body:
        if len(raw) != len(FUNDING_HEADER):
            raise OiFundingCorruptError(
                f"funding row has {len(raw)} columns, expected {len(FUNDING_HEADER)}"
            )
        calc_time_ms = _parse_int_ms(raw[0], field="calc_time")
        interval = _finite_decimal(raw[1], field="funding_interval_hours")
        if interval != Decimal(FUNDING_INTERVAL_HOURS):
            raise OiFundingCorruptError(
                f"funding interval mismatch: {interval!r} != {FUNDING_INTERVAL_HOURS}"
            )
        rate = _finite_decimal(raw[2], field="last_funding_rate")
        settlement = nearest_8h_settlement_ms(calc_time_ms)
        residual = abs(calc_time_ms - settlement)
        if residual > FUNDING_SETTLEMENT_SNAP_TOLERANCE_MS:
            raise OiFundingCorruptError(
                f"funding calc_time {calc_time_ms} is {residual}ms from 8h UTC"
            )
        if _utc_year_month(settlement) != requested_month:
            raise OiFundingCorruptError(
                f"funding row settlement {settlement} is outside requested "
                f"archive object {archive_object_name}"
            )
        row = NormalizedFundingRow(
            provider=PROVIDER,
            venue=VENUE,
            market_type=MARKET_TYPE,
            contract_type=CONTRACT_TYPE,
            symbol=SYMBOL,
            source_event_time_ms=calc_time_ms,
            period_start_ms=settlement - FUNDING_PERIOD_MS,
            period_end_ms=settlement,
            canonical_settlement_ms=settlement,
            publication_semantics_status=FUNDING_PUBLICATION_SEMANTICS_STATUS,
            legal_available_at_ms=None,
            funding_interval_hours=FUNDING_INTERVAL_HOURS,
            last_funding_rate=format(rate, "f"),
            funding_definition=FUNDING_DEFINITION,
            archive_object_name=archive_object_name,
        )
        prior = by_event.get(settlement)
        if prior is None:
            by_event[settlement] = (row, tuple(raw))
            continue
        prior_row, prior_raw = prior
        if prior_raw != tuple(raw):
            raise OiFundingCorruptError(
                f"conflicting duplicate funding settlement {settlement}"
            )
    return [by_event[key][0] for key in sorted(by_event)]


def normalize_oi_rows(
    csv_text: str,
    *,
    identity: Mapping[str, Any],
    archive_object_name: str,
    published_at_by_event_ms: Mapping[int, int] | None = None,
    oi_series_field: str = "sum_open_interest",
) -> list[NormalizedOiRow]:
    require_frozen_source(identity)
    requested_day = parse_oi_archive_day(archive_object_name)
    if oi_series_field != "sum_open_interest":
        raise OiFundingIdentityError(
            f"wrong OI series field {oi_series_field!r}; only sum_open_interest"
        )
    header, body = split_csv_rows(csv_text)
    _require_header(header, OI_HEADER, "open_interest")
    _reject_forbidden_identity(
        provider=str(identity["provider"]),
        venue=str(identity["venue"]),
        market_type=str(identity["market_type"]),
        contract_type=str(identity["contract_type"]),
        symbol=str(identity["symbol"]),
        oi_definition=str(identity["oi_definition"]),
        oi_units=str(identity["oi_units"]),
        oi_granularity=str(identity["oi_native_granularity"]),
    )

    grouped: dict[int, list[tuple[str, ...]]] = {}
    for raw in body:
        if len(raw) != len(OI_HEADER):
            raise OiFundingCorruptError(
                f"OI row has {len(raw)} columns, expected {len(OI_HEADER)}"
            )
        period_start_ms = parse_oi_create_time_ms(raw[0])
        if period_start_ms % OI_PERIOD_MS != 0:
            raise OiFundingCorruptError(
                f"OI create_time not on 5m UTC grid: {raw[0]!r}"
            )
        if _utc_day(period_start_ms) != requested_day:
            raise OiFundingCorruptError(
                f"OI row create_time {raw[0]!r} is outside requested "
                f"archive object {archive_object_name}"
            )
        row_symbol = raw[1]
        if row_symbol != SYMBOL:
            raise OiFundingIdentityError(f"wrong symbol in OI row: {row_symbol!r}")
        oi_value = _finite_decimal(raw[2], field="sum_open_interest")
        if oi_value < 0:
            raise OiFundingCorruptError("negative sum_open_interest is corrupt")
        grouped.setdefault(period_start_ms, []).append(tuple(raw))

    out: list[NormalizedOiRow] = []
    for period_start_ms in sorted(grouped):
        variants = grouped[period_start_ms]
        unique_payloads = set(variants)
        if len(unique_payloads) > 1:
            raise OiFundingCorruptError(
                f"conflicting duplicate OI timestamp {period_start_ms}"
            )
        collapsed = len(variants) > 1
        raw = variants[0]
        available_at = oi_available_at_ms(period_start_ms)
        published_at = available_at
        if published_at_by_event_ms and period_start_ms in published_at_by_event_ms:
            published_at = int(published_at_by_event_ms[period_start_ms])
        out.append(
            NormalizedOiRow(
                provider=PROVIDER,
                venue=VENUE,
                market_type=MARKET_TYPE,
                contract_type=CONTRACT_TYPE,
                symbol=SYMBOL,
                source_event_time_ms=period_start_ms,
                period_start_ms=period_start_ms,
                period_end_ms=period_start_ms + OI_PERIOD_MS,
                published_at_ms=published_at,
                available_at_ms=available_at,
                sum_open_interest=format(_finite_decimal(raw[2], field="sum_open_interest"), "f"),
                oi_definition=OI_DEFINITION,
                oi_units=OI_UNITS,
                oi_native_granularity=OI_NATIVE_GRANULARITY,
                identical_duplicate_collapsed=collapsed,
                archive_object_name=archive_object_name,
                duplicate_equality_rule=OI_DUPLICATE_EQUALITY_RULE,
            )
        )
    return out


def expected_oi_period_starts(day_yyyy_mm_dd: str) -> list[int]:
    match = _YEAR_MONTH_DAY_RE.fullmatch(day_yyyy_mm_dd)
    if not match:
        raise OiFundingCorruptError(f"OI day must be YYYY-MM-DD, got {day_yyyy_mm_dd!r}")
    year, month, day = (int(match.group(1)), int(match.group(2)), int(match.group(3)))
    start = datetime(year, month, day, tzinfo=UTC)
    start_ms = int(start.timestamp() * 1000)
    return [start_ms + i * OI_PERIOD_MS for i in range(288)]


def missing_oi_intervals(
    rows: Sequence[NormalizedOiRow],
    *,
    day_yyyy_mm_dd: str,
) -> list[int]:
    have = {row.period_start_ms for row in rows}
    missing = [ts for ts in expected_oi_period_starts(day_yyyy_mm_dd) if ts not in have]
    return missing


def expected_funding_settlements_ms(year_month: str) -> list[int]:
    match = _YEAR_MONTH_RE.fullmatch(year_month)
    if not match or not (1 <= int(match.group(2)) <= 12):
        raise OiFundingCorruptError(f"funding month must be YYYY-MM, got {year_month!r}")
    year, month = int(match.group(1)), int(match.group(2))
    start = datetime(year, month, 1, tzinfo=UTC)
    last_day = calendar.monthrange(year, month)[1]
    end_exclusive = datetime(year, month, last_day, tzinfo=UTC).timestamp() * 1000
    end_exclusive_ms = int(end_exclusive) + 24 * 60 * 60 * 1000
    start_ms = int(start.timestamp() * 1000)
    out: list[int] = []
    ts = start_ms
    while ts < end_exclusive_ms:
        out.append(ts)
        ts += FUNDING_PERIOD_MS
    return out


def _gap_ranges(missing: Sequence[int], step_ms: int) -> list[tuple[int, int]]:
    if not missing:
        return []
    ranges: list[tuple[int, int]] = []
    start = prev = missing[0]
    for ts in missing[1:]:
        if ts == prev + step_ms:
            prev = ts
            continue
        ranges.append((start, prev))
        start = prev = ts
    ranges.append((start, prev))
    return ranges


def funding_settlement_denominator(
    rows: Sequence[NormalizedFundingRow],
    *,
    year_month: str,
) -> dict[str, Any]:
    expected = expected_funding_settlements_ms(year_month)
    present = sorted({row.canonical_settlement_ms for row in rows})
    expected_set = set(expected)
    present_set = set(present)
    extra = sorted(present_set - expected_set)
    if extra:
        raise OiFundingCorruptError(
            f"funding settlements outside {year_month}: {extra[:5]}"
        )
    missing = [ts for ts in expected if ts not in present_set]
    return {
        "expected_settlements": expected,
        "present_valid_settlements": present,
        "missing_settlements": missing,
        "gap_count": len(missing),
        "gap_ranges": _gap_ranges(missing, FUNDING_PERIOD_MS),
    }


def classify_failure(exc: BaseException) -> str:
    if isinstance(exc, OiFundingCorruptError):
        return "CORRUPT"
    if isinstance(exc, OiFundingMissingError):
        return "MISSING"
    if isinstance(exc, OiFundingLookaheadError):
        return "NOT_READY"
    if isinstance(exc, OiFundingIdentityError):
        return "IDENTITY"
    if isinstance(exc, OiFundingSupportError):
        return "SUPPORT"
    if isinstance(exc, OiFundingAuthorizationError):
        return "AUTHORIZATION"
    raise exc


def refuse_reclassify_corrupt_as_missing(exc: BaseException) -> str:
    kind = classify_failure(exc)
    if kind == "CORRUPT":
        return "CORRUPT"
    if kind == "MISSING":
        return "MISSING"
    return kind


def last_legally_available(
    rows: Sequence[NormalizedOiRow] | Sequence[NormalizedFundingRow],
    *,
    decision_t_ms: int,
    max_staleness_ms: int,
) -> NormalizedOiRow | NormalizedFundingRow | None:
    usable = []
    for row in rows:
        if isinstance(row, NormalizedFundingRow):
            continue
        record = {
            "available_at_ms": row.available_at_ms,
            "published_at_ms": row.published_at_ms,
        }
        if not observation_usable_at(record=record, decision_t_ms=decision_t_ms):
            continue
        staleness = int(decision_t_ms) - int(row.available_at_ms)
        if staleness > max_staleness_ms:
            continue
        usable.append(row)
    if not usable:
        return None
    return max(usable, key=lambda item: (item.available_at_ms, item.source_event_time_ms))


def crowding_inputs_ready(
    *,
    oi_rows: Sequence[NormalizedOiRow],
    funding_rows: Sequence[NormalizedFundingRow],
    decision_t_ms: int,
) -> dict[str, Any]:
    for row in funding_rows:
        if row.publication_semantics_status == FUNDING_PUBLICATION_PROVEN_STATUS:
            raise OiFundingAuthorizationError(
                "caller cannot mark funding publication semantics as proven"
            )
        if row.legal_available_at_ms is not None:
            raise OiFundingAuthorizationError(
                "caller cannot supply funding legal_available_at while unproven"
            )
    oi = last_legally_available(
        oi_rows, decision_t_ms=decision_t_ms, max_staleness_ms=OI_MAX_STALENESS_MS
    )
    funding_block = FUNDING_PUBLICATION_SEMANTICS_STATUS
    if oi is None:
        return {
            "ready": False,
            "reason": "MISSING_OR_NOT_READY",
            "oi_ready": False,
            "funding_ready": False,
            "funding_block": funding_block,
        }
    return {
        "ready": False,
        "reason": FUNDING_PUBLICATION_SEMANTICS_STATUS,
        "oi_ready": True,
        "funding_ready": False,
        "funding_block": funding_block,
        "oi_available_at_ms": oi.available_at_ms,
    }


def eligible_decision_keys(
    *,
    candidate_keys: Sequence[Any],
    baseline_keys: Sequence[Any],
    oi_rows: Sequence[NormalizedOiRow],
    funding_rows: Sequence[NormalizedFundingRow],
    decision_t_by_key: Mapping[Any, int],
    price_legally_available_keys: Iterable[Any],
) -> tuple[Any, ...]:
    """Freeze same-support eligibility from inputs only (no outcomes)."""
    price_ok = set(price_legally_available_keys)
    candidate_set = list(candidate_keys)
    baseline_set = list(baseline_keys)
    if list(candidate_set) != list(baseline_set):
        raise OiFundingSupportError(
            "candidate and baseline key sequences must be declared identically "
            "before missingness filtering"
        )
    eligible: list[Any] = []
    for key in candidate_set:
        if key not in price_ok:
            continue
        if key not in decision_t_by_key:
            raise OiFundingCorruptError(f"missing decision time for key {key!r}")
        status = crowding_inputs_ready(
            oi_rows=oi_rows,
            funding_rows=funding_rows,
            decision_t_ms=int(decision_t_by_key[key]),
        )
        if status["ready"]:
            eligible.append(key)
    return tuple(eligible)


def pair_same_support(
    *,
    candidate_keys: Sequence[Any],
    baseline_keys: Sequence[Any],
    eligible_keys: Sequence[Any],
) -> tuple[Any, ...]:
    candidate = tuple(candidate_keys)
    baseline = tuple(baseline_keys)
    eligible = tuple(eligible_keys)
    if candidate != eligible or baseline != eligible:
        raise OiFundingSupportError(
            "candidate/baseline support mismatch: pairing is legal only on the "
            "predeclared eligible key set"
        )
    if set(candidate) != set(baseline):
        raise OiFundingSupportError("candidate and baseline key sets differ")
    return eligible


def mixed_batch_identity(records: Sequence[Mapping[str, Any]]) -> None:
    if not records:
        raise OiFundingMissingError("no records in batch")
    providers = {record.get("provider") for record in records}
    venues = {record.get("venue") for record in records}
    timeframes = {record.get("oi_native_granularity") or record.get("timeframe") for record in records}
    if len(providers) > 1:
        raise OiFundingIdentityError("mixed provider fallback is forbidden")
    if len(venues) > 1:
        raise OiFundingIdentityError("mixed venue fallback is forbidden")
    if len(timeframes) > 1:
        raise OiFundingIdentityError("mixed timeframe fallback is forbidden")
    for record in records:
        _reject_forbidden_identity(
            provider=str(record.get("provider")),
            venue=str(record.get("venue")),
            market_type=str(record.get("market_type", MARKET_TYPE)),
            contract_type=str(record.get("contract_type", CONTRACT_TYPE)),
            symbol=str(record.get("symbol", SYMBOL)),
            oi_granularity=record.get("oi_native_granularity"),
        )


def normalization_source_sha256(source_bytes: bytes) -> str:
    return sha256_hex(source_bytes)


def _require_40_hex(value: str, label: str) -> str:
    text = value.strip().lower()
    if len(text) != 40 or any(ch not in "0123456789abcdef" for ch in text):
        raise OiFundingAuthorizationError(f"{label} must be an exact 40-hex SHA")
    return text


def _require_repo_relative_git_path(git_path: str) -> str:
    if (
        not git_path
        or git_path.startswith("/")
        or ".." in Path(git_path).parts
        or Path(git_path).is_absolute()
    ):
        raise OiFundingAuthorizationError(f"invalid git authority path: {git_path!r}")
    return git_path


@dataclass(frozen=True)
class VerifiedOiFundingGitAuthority:
    repo_root: Path
    authority_commit_sha: str
    authority_tree_sha: str
    manifest_git_path: str
    normalization_git_path: str
    manifest: dict[str, Any]
    normalization_source_sha256: str
    code_freeze: VerifiedCodeFreeze
    _verification_token: object = field(default=None, repr=False, compare=False)

    def __post_init__(self) -> None:
        if self._verification_token is not _OI_FUNDING_GIT_TOKEN:
            raise OiFundingAuthorizationError(
                "VerifiedOiFundingGitAuthority must be created by "
                "verify_oi_funding_git_authority"
            )


def verify_oi_funding_git_authority(
    *,
    repo_root: Path,
    authority_commit_sha: str,
    authority_tree_sha: str,
    manifest_git_path: str = MANIFEST_PATH,
    normalization_git_path: str = NORMALIZATION_MODULE,
) -> VerifiedOiFundingGitAuthority:
    commit = _require_40_hex(authority_commit_sha, "authority_commit_sha")
    tree = _require_40_hex(authority_tree_sha, "authority_tree_sha")
    manifest_path = _require_repo_relative_git_path(manifest_git_path)
    normalization_path = _require_repo_relative_git_path(normalization_git_path)
    try:
        freeze = verify_git_freeze(Path(repo_root), commit)
    except CodeIdentityError as exc:
        raise OiFundingAuthorizationError(str(exc)) from exc
    if freeze.tree_oid != tree:
        raise OiFundingAuthorizationError(
            f"authority tree mismatch: {freeze.tree_oid} != {tree}"
        )
    try:
        manifest_bytes = read_frozen_git_bytes(freeze, manifest_path)
        normalization_bytes = read_frozen_git_bytes(freeze, normalization_path)
    except (CodeIdentityError, DatasetIdentityError) as exc:
        raise OiFundingAuthorizationError(str(exc)) from exc
    try:
        manifest = yaml.safe_load(manifest_bytes.decode("utf-8"))
    except (UnicodeDecodeError, yaml.YAMLError) as exc:
        raise OiFundingAuthorizationError("frozen manifest is not valid UTF-8 YAML") from exc
    if not isinstance(manifest, dict):
        raise OiFundingAuthorizationError("frozen manifest must be a mapping")
    if manifest.get("dataset_id") != DATASET_ID:
        raise OiFundingIdentityError("tracked manifest dataset_id mismatch")
    if manifest.get("snapshot_id") not in (None, "NOT_MATERIALIZED"):
        raise OiFundingAuthorizationError(
            "unmaterialized dataset snapshot_id must remain NOT_MATERIALIZED"
        )
    if manifest.get("research_authorized") is not False:
        raise OiFundingAuthorizationError("research_authorized must be false")
    if manifest.get("outcome_access_authorized") not in (False, None):
        raise OiFundingAuthorizationError("outcome access is not authorized")
    return VerifiedOiFundingGitAuthority(
        repo_root=freeze.repo_root,
        authority_commit_sha=freeze.code_sha,
        authority_tree_sha=freeze.tree_oid,
        manifest_git_path=manifest_path,
        normalization_git_path=normalization_path,
        manifest=manifest,
        normalization_source_sha256=sha256_hex(normalization_bytes),
        code_freeze=freeze,
        _verification_token=_OI_FUNDING_GIT_TOKEN,
    )


def require_normalization_identity(
    *,
    git_authority: VerifiedOiFundingGitAuthority,
    claimed_sha256: str | None = None,
    source_bytes: bytes | None = None,
    caller_source_bytes: bytes | None = None,
) -> str:
    if source_bytes is not None or caller_source_bytes is not None:
        raise OiFundingAuthorizationError(
            "caller-supplied normalization bytes are not Git authority"
        )
    if not isinstance(git_authority, VerifiedOiFundingGitAuthority):
        raise OiFundingAuthorizationError(
            "normalization identity requires verify_oi_funding_git_authority proof"
        )
    refreshed = verify_oi_funding_git_authority(
        repo_root=git_authority.repo_root,
        authority_commit_sha=git_authority.authority_commit_sha,
        authority_tree_sha=git_authority.authority_tree_sha,
        manifest_git_path=git_authority.manifest_git_path,
        normalization_git_path=git_authority.normalization_git_path,
    )
    actual = refreshed.normalization_source_sha256
    if claimed_sha256 is None:
        raise OiFundingCorruptError("missing normalization code identity")
    if claimed_sha256 != actual:
        raise OiFundingCorruptError(
            "normalization code identity mismatch: "
            f"{claimed_sha256} != {actual}"
        )
    return actual


def bind_snapshot_to_tracked_authority(
    *,
    git_authority: VerifiedOiFundingGitAuthority,
    snapshot: Mapping[str, Any] | None = None,
    claimed_snapshot_id: str | None = None,
    claimed_manifest: Mapping[str, Any] | None = None,
    tracked_manifest: Mapping[str, Any] | None = None,
    authority_kind: str = SNAPSHOT_AUTHORITY_KIND,
) -> str:
    if authority_kind != SNAPSHOT_AUTHORITY_KIND:
        raise OiFundingAuthorizationError(
            f"caller-selected snapshot authority is forbidden: {authority_kind!r}"
        )
    if tracked_manifest is not None or claimed_manifest is not None:
        raise OiFundingAuthorizationError(
            "caller-supplied manifest mapping is not Git authority"
        )
    if not isinstance(git_authority, VerifiedOiFundingGitAuthority):
        raise OiFundingAuthorizationError(
            "snapshot binding requires verify_oi_funding_git_authority proof"
        )
    refreshed = verify_oi_funding_git_authority(
        repo_root=git_authority.repo_root,
        authority_commit_sha=git_authority.authority_commit_sha,
        authority_tree_sha=git_authority.authority_tree_sha,
        manifest_git_path=git_authority.manifest_git_path,
        normalization_git_path=git_authority.normalization_git_path,
    )
    manifest = refreshed.manifest
    if manifest.get("status") != CONTRACT_STATUS:
        raise OiFundingAuthorizationError(
            f"tracked manifest status must remain {CONTRACT_STATUS}, got "
            f"{manifest.get('status')!r}"
        )
    if manifest.get("research_authorized") is not False:
        raise OiFundingAuthorizationError("research_authorized must be false")
    if manifest.get("confirmatory_authorized") is not False:
        raise OiFundingAuthorizationError("confirmatory_authorized must be false")
    if manifest.get("outcome_access_authorized") not in (False, None):
        raise OiFundingAuthorizationError("outcome access is not authorized")
    if manifest.get("b2_06_evaluator_enabled") not in (False, None):
        raise OiFundingAuthorizationError("scientific evaluator is not authorized")
    if manifest.get("snapshot_id") not in (None, "NOT_MATERIALIZED"):
        raise OiFundingAuthorizationError("snapshot substitution is forbidden")
    if claimed_snapshot_id not in (None, "NOT_MATERIALIZED"):
        raise OiFundingAuthorizationError(
            "unmaterialized dataset cannot accept a caller-chosen snapshot_id"
        )
    if snapshot is not None and snapshot.get("snapshot_id") not in (
        None,
        "NOT_MATERIALIZED",
    ):
        raise OiFundingAuthorizationError(
            "unmaterialized dataset cannot accept a caller-chosen snapshot_id"
        )
    return "NOT_MATERIALIZED"


def build_snapshot_identity(
    *,
    contract_sha256: str,
    normalization_source_sha256_hex: str,
    source_objects: Sequence[Mapping[str, Any]],
    normalized_objects: Sequence[Mapping[str, Any]],
    requested_intervals: Mapping[str, Any],
    retrieval_time_utc: str,
    row_counts: Mapping[str, int],
    first_last_timestamps: Mapping[str, Mapping[str, str]],
    provenance_git_commit_sha: str,
) -> dict[str, Any]:
    """Snapshot_id is computed from the payload. Callers cannot supply it."""
    payload = {
        "dataset_id": DATASET_ID,
        "contract_path": CONTRACT_PATH,
        "contract_sha256": contract_sha256,
        "schema_version": SCHEMA_VERSION,
        "availability_semantics_version": AVAILABILITY_SEMANTICS_VERSION,
        "normalization_version": NORMALIZATION_VERSION,
        "retrieval_method_version": RETRIEVAL_METHOD_VERSION,
        "snapshot_identity_version": SNAPSHOT_IDENTITY_VERSION,
        "normalization_module": NORMALIZATION_MODULE,
        "normalization_source_sha256": normalization_source_sha256_hex,
        "source_identity": dict(FROZEN_SOURCE),
        "requested_intervals": dict(requested_intervals),
        "retrieval_time_utc": retrieval_time_utc,
        "source_object_identities": list(source_objects),
        "normalized_object_identities": list(normalized_objects),
        "row_counts": dict(row_counts),
        "first_last_timestamps": dict(first_last_timestamps),
        "provenance_git_commit_sha": provenance_git_commit_sha,
        "research_authorized": False,
        "confirmatory_authorized": False,
        "outcome_access_authorized": False,
    }
    snapshot_id = sha256_of_canonical_identity_payload(payload)
    return {"snapshot_id": snapshot_id, "identity_payload": payload}


def assert_outcome_access_closed(manifest: Mapping[str, Any]) -> None:
    if manifest.get("outcome_access_authorized"):
        raise OiFundingAuthorizationError("B2-06 outcome access is not authorized")
    if manifest.get("research_authorized"):
        raise OiFundingAuthorizationError(
            "OI/funding dataset is not research-authorized until materialization"
        )
    if manifest.get("b2_06_evaluator_enabled"):
        raise OiFundingAuthorizationError("scientific evaluator is not authorized")


def validate_archive_zip_members(
    zip_bytes: bytes,
    *,
    expected_member_name: str,
) -> bytes:
    """Fail-closed ZIP member identity for a future materializer.

    Does not download or evaluate market outcomes. Rejects unexpected names,
    extra/hidden CSVs, duplicates, traversal, absolute paths, and non-UTF-8.
    """
    if not expected_member_name or "/" in expected_member_name or "\\" in expected_member_name:
        raise OiFundingCorruptError(
            f"expected ZIP member must be a basename, got {expected_member_name!r}"
        )
    try:
        archive = zipfile.ZipFile(io.BytesIO(zip_bytes))
    except zipfile.BadZipFile as exc:
        raise OiFundingCorruptError("unsupported compression/container shape") from exc
    names = archive.namelist()
    if len(names) != len(set(names)):
        raise OiFundingCorruptError("duplicate ZIP member names")
    for name in names:
        parts = Path(name.replace("\\", "/")).parts
        if name.startswith("/") or name.startswith("\\") or name.startswith("\\\\"):
            raise OiFundingCorruptError(f"absolute ZIP member path: {name!r}")
        if ".." in parts:
            raise OiFundingCorruptError(f"ZIP path traversal: {name!r}")
    csv_members = [name for name in names if name.lower().endswith(".csv")]
    if len(csv_members) != 1:
        raise OiFundingCorruptError(
            f"ZIP must contain exactly one CSV member, got {csv_members!r}"
        )
    member = csv_members[0]
    if member != expected_member_name:
        raise OiFundingCorruptError(
            f"unexpected ZIP member filename: {member!r} != {expected_member_name!r}"
        )
    extra = [name for name in names if name != member]
    if extra:
        raise OiFundingCorruptError(f"extra ZIP members are forbidden: {extra!r}")
    info = archive.getinfo(member)
    if info.is_dir():
        raise OiFundingCorruptError("ZIP CSV member must be a file")
    raw = archive.read(member)
    try:
        raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise OiFundingCorruptError("malformed UTF-8 in ZIP CSV member") from exc
    return raw


def funding_object_name(year_month: str) -> str:
    match = _YEAR_MONTH_RE.fullmatch(year_month)
    if not match or not (1 <= int(match.group(2)) <= 12):
        raise OiFundingCorruptError(f"funding month must be YYYY-MM, got {year_month!r}")
    year, month = int(match.group(1)), int(match.group(2))
    return FUNDING_OBJECT_TEMPLATE.format(year=year, month=month)


def oi_object_name(day: str) -> str:
    match = _YEAR_MONTH_DAY_RE.fullmatch(day)
    if not match:
        raise OiFundingCorruptError(f"OI day must be YYYY-MM-DD, got {day!r}")
    year, month, day_n = int(match.group(1)), int(match.group(2)), int(match.group(3))
    return OI_OBJECT_TEMPLATE.format(year=year, month=month, day=day_n)


def funding_urls(year_month: str) -> tuple[str, str]:
    name = funding_object_name(year_month)
    base = f"{ARCHIVE_ROOT}/{FUNDING_SERIES_PREFIX}/{name}"
    return base, f"{base}.CHECKSUM"


def oi_urls(day: str) -> tuple[str, str]:
    name = oi_object_name(day)
    base = f"{ARCHIVE_ROOT}/{OI_SERIES_PREFIX}/{name}"
    return base, f"{base}.CHECKSUM"
