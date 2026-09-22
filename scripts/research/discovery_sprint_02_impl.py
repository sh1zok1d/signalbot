"""Discovery Sprint 02 implementation: D7/D8 selectors and dormant evaluators.

Selector/support constructions may run on legal CORE BTC 2020-2024.
Scientific persistence/recovery evaluators are pure functions for synthetic
tests and must not be invoked on real CORE in this unit.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np


UTC = timezone.utc

UNIT = "DISCOVERY_SPRINT_02_FEASIBILITY_AND_IMPLEMENTATION"
CORE_BTC_DATASET_ID = "CORE_BTC_BINANCE_V0"
CORE_BTC_SNAPSHOT_ID = (
    "717d37a404f81eefd58c9a796cc11868c48226baf1de8ffecad5e5607f8dd415"
)
CORE_BTC_ROOT_REL = "artifacts/research_data/CORE_BTC_BINANCE_V0"
CORE_BTC_SNAPSHOT_DOC_REL = "docs/research_data/CORE_BTC_BINANCE_V0/SNAPSHOT_717d37a4.json"
CORE_BTC_MANIFEST_REL = "docs/manifests/CORE_BTC_BINANCE_V0.yaml"
RUNTIME_MANIFEST_RELS = (
    "artifacts/research_data/CORE_BTC_BINANCE_V0/reports/snapshot_manifest.json",
    "artifacts/research_data/CORE_BTC_BINANCE_V0/snapshot_manifest.json",
)
DATA_IDENTITY_MODE = "TRACKED_SNAPSHOT_FULL_MONTHLY_EXACT_BYTE_VERIFICATION"
RUNTIME_MANIFEST_ABSENCE_MEANING = (
    "NOT REQUIRED UNDER THIS FULL_EXACT_BYTE_IDENTITY_MODE"
)
MANIFEST_ACCEPTED_STATUS = "ACCEPTED_FOR_DISCOVERY"

D7_SELECTOR_N = 4545
D7_SELECTOR_DIGEST = (
    "8794fece9541c9b09f3ed83f09a9aaf8e4d1caf5df7c6fb8ef29ba6c54889b5b"
)
D7_CONSTRUCTED_HOURS = 43848
D7_VALID_IMPACT_ROWS = 43127
D7_TARGET_ELIGIBLE_ROWS = 42407

D8_STATUS = "DEFERRED_INSUFFICIENT_CONTROL_SUPPORT"
D8_SCIENTIFIC_EXECUTION_ELIGIBLE = False
D8_NOT_NO_USEFUL_STRUCTURE = True
D8_SCIENTIFIC_RECOVERY_HYPOTHESIS_EVALUATED = False
FROZEN_D8_RAW_RETURN_SHOCK_N = 547
FROZEN_D8_RAW_EVENT_N = 528
FROZEN_D8_RETAINED_EVENT_N = 408
FROZEN_D8_RAW_CONTROL_N = 19
FROZEN_D8_RETAINED_CONTROL_N = 18
FROZEN_D8_MATCHED_PAIR_N = 14
FROZEN_D8_UNMATCHED_EVENT_N = 394
FROZEN_LEGAL_MONTHLY_CHECKSUM_MAP_SHA256 = (
    "867979237169c2f3b7355d497670f03da7fd4e54bc3200e1003b317bd9dce483"
)
SPRINT_JSON_REL = "docs/research/DISCOVERY_SPRINT_02.json"
POLICY_JSON_REL = "docs/research/HETEROGENEOUS_FAMILY_ROTATION_V1.json"
DATA_POLICY_JSON_REL = "docs/research/HYPOTHESIS_GENERATION_POLICY_V2_DATA_ACQUISITION.json"

LEGAL_MONTHS = tuple(
    f"{year:04d}-{month:02d}" for year in range(2020, 2025) for month in range(1, 13)
)
REQUIRED_1M_COLUMNS = (
    "open_time_ms",
    "available_at_ms",
    "open",
    "close",
    "quote_volume",
    "trade_count",
    "taker_buy_quote_volume",
)
FORBIDDEN_1M_COLUMNS = ("close_time_ms",)

BAR_MS = 60_000
HOUR_MS = 3_600_000
BARS_PER_HOUR = 60
PROTECTED_START = datetime(2025, 1, 1, tzinfo=UTC)
PROTECTED_START_MS = int(PROTECTED_START.timestamp() * 1000)
LEGAL_START_MS = int(datetime(2020, 1, 1, tzinfo=UTC).timestamp() * 1000)
RECOVERY_6H_MS = 6 * HOUR_MS
RECOVERY_24H_MS = 24 * HOUR_MS
TRAILING_WINDOW = 720
EVENT_GAP_HOURS = 6
EVENT_GAP_MS = EVENT_GAP_HOURS * HOUR_MS

D7_PCTL = 90.0
D8_RETURN_PCTL = 99.0
D8_VOLUME_PCTL = 90.0
RV_CUTS = (25.0, 50.0, 75.0)
N_RV_BUCKETS = 4

D7_SEED = 20260922171
D8_SEED = 20260922172
N_RANDOM_CONTROLS = 10_000
N_RANDOMIZATIONS = 10_000
D7_PRACTICAL_GATE = 0.05
D8_PRACTICAL_GATE = 0.20
D8_MC_ALPHA = 0.05
D7_TEMPORAL_YEARS_REQUIRED = 3
D7_TEMPORAL_YEARS_TOTAL = 5
D8_TEMPORAL_YEARS_REQUIRED = 2
D8_TEMPORAL_MIN_PAIRS = 3

MIN_D7_STATE_TOTAL = 500
MIN_D7_STATE_PER_YEAR = 50
MIN_NONOVERLAPPING_EVENTS = 20
MIN_YEARS_WITH_EVENTS = 3
MIN_EVENTS_PER_YEAR_IN_AT_LEAST_TWO_YEARS = 3
CONTROL_YEARS = (2020, 2021, 2022, 2023, 2024)

PERCENTILE_METHOD = "linear"

_PROTECTED_PERIOD_RE = re.compile(r"(?:^|[^0-9])(2025|2026)-\d{2}")


class ProtectedYearRefused(RuntimeError):
    """Opening a 2025/2026 partition or timestamp was refused."""


class SnapshotIdentityError(RuntimeError):
    """Opened files do not match the frozen snapshot identity."""


class MissingLocalData(RuntimeError):
    """Required frozen local snapshot material is absent."""


class Sprint02IntegrityError(RuntimeError):
    """Frozen Sprint 02 contract was violated."""


class RealScientificOutcomeForbidden(RuntimeError):
    """Real-data D7/D8 scientific outcomes are forbidden in this unit."""


class SelectorIdentityError(RuntimeError):
    """Frozen D7 selector identity was violated."""


@dataclass(frozen=True)
class MinuteBar:
    open_time_ms: int
    available_at_ms: int
    open: float
    close: float
    quote_volume: float
    trade_count: int
    taker_buy_quote_volume: float


@dataclass(frozen=True)
class HourBar:
    hour_start_ms: int
    available_at_ms: int
    year: int
    open_1h: float
    close_1h: float
    quote_volume_1h: float
    trade_count_1h: int
    taker_buy_quote_volume_1h: float
    ret_abs_1h: float
    event_return: float


@dataclass
class D7HourState:
    hour: HourBar
    qrel_1h: float | None
    impact_proxy: float | None
    d7_state: bool | None
    rv_bucket: int | None


@dataclass(frozen=True)
class D8RawCandidate:
    hour: HourBar
    abs_event_return: float
    event_sign: int
    event_volume: float
    p99_return: float
    p90_volume: float
    is_event: bool
    is_control: bool
    is_return_shock: bool


@dataclass
class OpenedFileLog:
    files: list[str] = field(default_factory=list)

    def record(self, path: Path, *, repo_root: Path) -> None:
        try:
            rel = str(path.resolve().relative_to(repo_root.resolve()))
        except ValueError:
            rel = str(path)
        self.files.append(rel)


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def file_sha256(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def canonical_json(obj: Any) -> str:
    return json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def parse_decimal_string(value: Any, *, field: str) -> float:
    if isinstance(value, bytes):
        value = value.decode("utf-8")
    if not isinstance(value, str):
        raise Sprint02IntegrityError(f"NON_STRING_DECIMAL:{field}:{type(value).__name__}")
    if not re.fullmatch(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?", value):
        raise Sprint02IntegrityError(f"LEXICAL_OR_MALFORMED_DECIMAL:{field}:{value!r}")
    out = float(Decimal(value))
    if not math.isfinite(out):
        raise Sprint02IntegrityError(f"NONFINITE_DECIMAL:{field}:{value!r}")
    return out


def path_is_protected_partition(path: Path) -> bool:
    for part in path.parts:
        if _PROTECTED_PERIOD_RE.search(part):
            return True
        if part.startswith("2025-") or part.startswith("2026-"):
            return True
    return False


def legal_monthly_parquet_path(dataset_root: Path, period: str) -> Path:
    if period.startswith("2025-") or period.startswith("2026-"):
        raise ProtectedYearRefused(f"PROTECTED_MONTH_REFUSED_BEFORE_READ:{period}")
    if period not in LEGAL_MONTHS:
        raise ProtectedYearRefused(f"NON_LEGAL_MONTH_REFUSED_BEFORE_READ:{period}")
    path = dataset_root / "canonical" / "1m" / "monthly" / f"{period}.parquet"
    if path_is_protected_partition(path):
        raise ProtectedYearRefused(f"PROTECTED_PARTITION_REFUSED_BEFORE_READ:{path}")
    return path


def _yaml_top_level_scalar(text: str, key: str) -> str:
    prefix = f"{key}:"
    for line in text.splitlines():
        if line.startswith(" ") or line.startswith("\t"):
            continue
        stripped = line.strip()
        if stripped.startswith(prefix):
            return stripped.split(":", 1)[1].strip().strip("'\"")
    raise SnapshotIdentityError(f"MANIFEST_{key.upper()}_MISSING")


def _yaml_top_level_bool(text: str, key: str) -> bool:
    raw = _yaml_top_level_scalar(text, key)
    lowered = raw.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    raise SnapshotIdentityError(f"MANIFEST_{key.upper()}_NOT_BOOL:{raw}")


def parse_core_manifest(text: str) -> dict[str, Any]:
    return {
        "dataset_id": _yaml_top_level_scalar(text, "dataset_id"),
        "status": _yaml_top_level_scalar(text, "status"),
        "current_state": _yaml_top_level_scalar(text, "current_state"),
        "research_authorized": _yaml_top_level_bool(text, "research_authorized"),
        "confirmatory_authorized": _yaml_top_level_bool(text, "confirmatory_authorized"),
        "snapshot_id": _yaml_top_level_scalar(text, "snapshot_id"),
    }


def legal_monthly_checksum_key(period: str) -> str:
    return f"canonical/1m/monthly/{period}.parquet"


def legal_monthly_checksum_subset(checksums: Mapping[str, str]) -> dict[str, str]:
    return {
        legal_monthly_checksum_key(period): str(checksums[legal_monthly_checksum_key(period)])
        for period in LEGAL_MONTHS
    }


def legal_monthly_checksum_map_sha256(checksums: Mapping[str, str]) -> str:
    return sha256_bytes(canonical_json(legal_monthly_checksum_subset(checksums)).encode("utf-8"))


def assert_tracked_legal_monthly_checksums(
    checksums: Mapping[str, str],
    *,
    require_frozen_map: bool = True,
) -> None:
    if tuple(LEGAL_MONTHS) != tuple(
        f"{year:04d}-{month:02d}" for year in range(2020, 2025) for month in range(1, 13)
    ):
        raise Sprint02IntegrityError("LEGAL_MONTHS_NOT_2020_01_2024_12")
    if len(LEGAL_MONTHS) != 60:
        raise Sprint02IntegrityError(f"LEGAL_MONTH_COUNT:{len(LEGAL_MONTHS)}!=60")
    missing: list[str] = []
    for period in LEGAL_MONTHS:
        digest = checksums.get(legal_monthly_checksum_key(period))
        if digest is None or digest == "":
            missing.append(period)
            continue
        if not re.fullmatch(r"[0-9a-f]{64}", str(digest)):
            raise SnapshotIdentityError(f"ILLEGAL_CHECKSUM_FORMAT:{period}:{digest}")
    if missing:
        raise SnapshotIdentityError(f"MISSING_FROZEN_CHECKSUM:{','.join(missing)}")
    if require_frozen_map:
        got = legal_monthly_checksum_map_sha256(checksums)
        if got != FROZEN_LEGAL_MONTHLY_CHECKSUM_MAP_SHA256:
            raise SnapshotIdentityError(f"LEGAL_MONTHLY_CHECKSUM_MAP_MISMATCH:{got}")


def verify_dataset_authority(
    repo: Path,
    *,
    snapshot_doc: Path | None = None,
    manifest: Path | None = None,
) -> dict[str, Any]:
    snapshot_path = snapshot_doc if snapshot_doc is not None else repo / CORE_BTC_SNAPSHOT_DOC_REL
    manifest_path = manifest if manifest is not None else repo / CORE_BTC_MANIFEST_REL
    if not snapshot_path.is_file():
        raise MissingLocalData(f"MISSING_SNAPSHOT_DOC:{snapshot_path}")
    if not manifest_path.is_file():
        raise MissingLocalData(f"MISSING_DATASET_MANIFEST:{manifest_path}")
    identity = json.loads(snapshot_path.read_text(encoding="utf-8"))
    payload = identity.get("identity_payload") or identity
    bound = str(payload.get("snapshot_id") or identity.get("snapshot_id") or "")
    if bound != CORE_BTC_SNAPSHOT_ID:
        raise SnapshotIdentityError(f"REPO_SNAPSHOT_MISMATCH:{bound}")
    parsed = parse_core_manifest(manifest_path.read_text(encoding="utf-8"))
    if parsed["snapshot_id"] != CORE_BTC_SNAPSHOT_ID:
        raise SnapshotIdentityError(f"YAML_SNAPSHOT_MISMATCH:{parsed['snapshot_id']}")
    if parsed["dataset_id"] != CORE_BTC_DATASET_ID:
        raise SnapshotIdentityError(f"YAML_DATASET_ID_MISMATCH:{parsed['dataset_id']}")
    if parsed["status"] != MANIFEST_ACCEPTED_STATUS:
        raise SnapshotIdentityError(f"YAML_STATUS_MISMATCH:{parsed['status']}")
    if parsed["current_state"] != MANIFEST_ACCEPTED_STATUS:
        raise SnapshotIdentityError(
            f"YAML_CURRENT_STATE_MISMATCH:{parsed['current_state']}"
        )
    if parsed["research_authorized"] is not True:
        raise SnapshotIdentityError(
            f"YAML_RESEARCH_AUTHORIZED_MISMATCH:{parsed['research_authorized']}"
        )
    if parsed["confirmatory_authorized"] is not False:
        raise SnapshotIdentityError(
            f"YAML_CONFIRMATORY_AUTHORIZED_MISMATCH:{parsed['confirmatory_authorized']}"
        )
    runtime_rel = None
    runtime_id = None
    for rel in RUNTIME_MANIFEST_RELS:
        path = repo / rel
        if path.is_file():
            runtime_rel = rel
            runtime_obj = json.loads(path.read_text(encoding="utf-8"))
            runtime_payload = runtime_obj.get("identity_payload") or runtime_obj
            runtime_id = str(
                runtime_payload.get("snapshot_id") or runtime_obj.get("snapshot_id") or ""
            )
            if runtime_id != CORE_BTC_SNAPSHOT_ID:
                raise SnapshotIdentityError(f"RUNTIME_SNAPSHOT_MISMATCH:{runtime_id}")
            break
    checksums = dict(payload.get("output_checksums") or {})
    assert_tracked_legal_monthly_checksums(checksums)
    runtime_found = runtime_rel is not None
    return {
        "DATA_IDENTITY_MODE": DATA_IDENTITY_MODE,
        "CORE_BTC_SNAPSHOT_ID": CORE_BTC_SNAPSHOT_ID,
        "CORE_BTC_DATASET_ID": CORE_BTC_DATASET_ID,
        "REPO_SNAPSHOT_DOC": CORE_BTC_SNAPSHOT_DOC_REL,
        "DATASET_MANIFEST": CORE_BTC_MANIFEST_REL,
        "MANIFEST_DATASET_ID": parsed["dataset_id"],
        "MANIFEST_STATUS": parsed["status"],
        "MANIFEST_CURRENT_STATE": parsed["current_state"],
        "MANIFEST_RESEARCH_AUTHORIZED": parsed["research_authorized"],
        "MANIFEST_CONFIRMATORY_AUTHORIZED": parsed["confirmatory_authorized"],
        "RUNTIME_SNAPSHOT_MANIFEST": runtime_rel,
        "RUNTIME_SNAPSHOT_MANIFEST_FOUND": runtime_found,
        "RUNTIME_SNAPSHOT_MANIFEST_ABSENCE": (
            None if runtime_found else RUNTIME_MANIFEST_ABSENCE_MEANING
        ),
        "FULL_MONTHLY_EXACT_BYTE_VERIFICATION": True,
        "LEGAL_MONTH_COUNT": len(LEGAL_MONTHS),
        "output_checksums": checksums,
    }


def percentile(values: Sequence[float], p: float) -> float:
    arr = np.asarray(list(values), dtype=np.float64)
    if arr.size == 0:
        raise Sprint02IntegrityError("EMPTY_PERCENTILE")
    return float(np.percentile(arr, p, method=PERCENTILE_METHOD))


def median(values: Sequence[float]) -> float:
    arr = np.asarray(list(values), dtype=np.float64)
    if arr.size == 0:
        raise Sprint02IntegrityError("EMPTY_MEDIAN")
    return float(np.median(arr))


def rv_bucket_from_trailing(rv: float, trailing: Sequence[float]) -> int:
    if len(trailing) < TRAILING_WINDOW:
        raise Sprint02IntegrityError("RV_BUCKET_SHORT_WINDOW")
    p25, p50, p75 = (
        percentile(trailing, RV_CUTS[0]),
        percentile(trailing, RV_CUTS[1]),
        percentile(trailing, RV_CUTS[2]),
    )
    if rv <= p25:
        return 0
    if rv <= p50:
        return 1
    if rv <= p75:
        return 2
    return 3


def load_legal_1m_bars(
    *,
    repo: Path | None = None,
    dataset_root: Path | None = None,
    checksums: Mapping[str, str] | None = None,
    log: OpenedFileLog | None = None,
    require_repo_authority: bool = True,
) -> list[MinuteBar]:
    base = repo or repo_root()
    authority = verify_dataset_authority(base) if require_repo_authority else {
        "output_checksums": dict(checksums or {}),
    }
    root = dataset_root if dataset_root is not None else base / CORE_BTC_ROOT_REL
    if not root.is_dir():
        raise MissingLocalData(f"MISSING_CORE_ROOT:{root}")
    bound_checksums = dict(checksums) if checksums is not None else authority["output_checksums"]
    assert_tracked_legal_monthly_checksums(
        bound_checksums, require_frozen_map=require_repo_authority
    )
    opened = log if log is not None else OpenedFileLog()
    bars: list[MinuteBar] = []
    for period in LEGAL_MONTHS:
        path = legal_monthly_parquet_path(root, period)
        if not path.is_file():
            raise MissingLocalData(f"MISSING_MONTH:{period}")
        # Exact-byte identity: SHA256 of parquet bytes must match the tracked
        # snapshot before pyarrow parses any scientific columns.
        raw = path.read_bytes()
        expected = bound_checksums.get(legal_monthly_checksum_key(period))
        if expected is None:
            raise SnapshotIdentityError(f"MISSING_FROZEN_CHECKSUM:{period}")
        if sha256_bytes(raw) != expected:
            raise SnapshotIdentityError(f"CHECKSUM_MISMATCH:{period}")
        opened.record(path, repo_root=base)
        bars.extend(_read_legal_parquet(path))
    bars.sort(key=lambda bar: bar.open_time_ms)
    return bars


def _read_legal_parquet(path: Path) -> list[MinuteBar]:
    import pyarrow.parquet as pq

    names = set(pq.read_schema(path).names)
    if "close_time_ms" in names and "close_time_ms" in FORBIDDEN_1M_COLUMNS:
        # Column may exist on disk; it must not be loaded.
        pass
    missing = [name for name in REQUIRED_1M_COLUMNS if name not in names]
    if missing:
        raise Sprint02IntegrityError(f"PARQUET_SCHEMA_MISSING:{path}:{missing}")
    table = pq.read_table(path, columns=list(REQUIRED_1M_COLUMNS))
    if "close_time_ms" in table.column_names:
        raise Sprint02IntegrityError(f"CLOSE_TIME_MS_LOADED:{path}")
    opens = table.column("open_time_ms").to_pylist()
    available = table.column("available_at_ms").to_pylist()
    open_px = table.column("open").to_pylist()
    close_px = table.column("close").to_pylist()
    quote = table.column("quote_volume").to_pylist()
    trades = table.column("trade_count").to_pylist()
    taker = table.column("taker_buy_quote_volume").to_pylist()
    out: list[MinuteBar] = []
    for i, open_ms_raw in enumerate(opens):
        open_ms = int(open_ms_raw)
        avail_ms = int(available[i])
        if open_ms >= PROTECTED_START_MS:
            raise ProtectedYearRefused(f"PROTECTED_TIMESTAMP:{path}:{open_ms}")
        if avail_ms > PROTECTED_START_MS:
            raise ProtectedYearRefused(f"PROTECTED_AVAILABLE_AT:{path}:{avail_ms}")
        if open_ms < LEGAL_START_MS:
            continue
        if avail_ms != open_ms + BAR_MS:
            raise Sprint02IntegrityError(
                f"AVAILABLE_AT_MISMATCH:{path}:{open_ms}:{avail_ms}"
            )
        out.append(
            MinuteBar(
                open_time_ms=open_ms,
                available_at_ms=avail_ms,
                open=parse_decimal_string(open_px[i], field="open"),
                close=parse_decimal_string(close_px[i], field="close"),
                quote_volume=parse_decimal_string(quote[i], field="quote_volume"),
                trade_count=int(trades[i]),
                taker_buy_quote_volume=parse_decimal_string(
                    taker[i], field="taker_buy_quote_volume"
                ),
            )
        )
    return out


def aggregate_completed_hours(bars: Sequence[MinuteBar]) -> list[HourBar]:
    by_open = {int(bar.open_time_ms): bar for bar in bars}
    if not by_open:
        return []
    hours: list[HourBar] = []
    hour_start = min(by_open) - (min(by_open) % HOUR_MS)
    last = max(by_open)
    while hour_start < PROTECTED_START_MS:
        members: list[MinuteBar] = []
        complete = True
        for k in range(BARS_PER_HOUR):
            want = hour_start + k * BAR_MS
            bar = by_open.get(want)
            if bar is None:
                complete = False
                break
            members.append(bar)
        if complete:
            first = members[0]
            last_bar = members[-1]
            if last_bar.available_at_ms != hour_start + HOUR_MS:
                raise Sprint02IntegrityError(
                    f"HOUR_AVAILABLE_AT:{hour_start}:{last_bar.available_at_ms}"
                )
            if first.open <= 0.0 or last_bar.close <= 0.0:
                hour_start += HOUR_MS
                continue
            event_return = math.log(last_bar.close / first.open)
            if not math.isfinite(event_return):
                hour_start += HOUR_MS
                continue
            quote_sum = sum(bar.quote_volume for bar in members)
            hours.append(
                HourBar(
                    hour_start_ms=hour_start,
                    available_at_ms=hour_start + HOUR_MS,
                    year=datetime.fromtimestamp(hour_start / 1000.0, tz=UTC).year,
                    open_1h=first.open,
                    close_1h=last_bar.close,
                    quote_volume_1h=quote_sum,
                    trade_count_1h=sum(bar.trade_count for bar in members),
                    taker_buy_quote_volume_1h=sum(
                        bar.taker_buy_quote_volume for bar in members
                    ),
                    ret_abs_1h=abs(event_return),
                    event_return=event_return,
                )
            )
        hour_start += HOUR_MS
    return hours


def build_d7_states(hours: Sequence[HourBar]) -> list[D7HourState]:
    states: list[D7HourState] = []
    valid_volumes: list[float] = []
    valid_impacts: list[float] = []
    valid_rvs: list[float] = []
    for hour in hours:
        qrel = None
        impact = None
        state = None
        bucket = None
        vol_ok = math.isfinite(hour.quote_volume_1h)
        rv_ok = math.isfinite(hour.ret_abs_1h)
        if vol_ok and len(valid_volumes) >= TRAILING_WINDOW:
            med = median(valid_volumes[-TRAILING_WINDOW:])
            if math.isfinite(med) and med > 0.0 and hour.quote_volume_1h > 0.0:
                qrel = hour.quote_volume_1h / med
                if math.isfinite(qrel) and qrel > 0.0 and rv_ok:
                    impact = hour.ret_abs_1h / qrel
                    if not math.isfinite(impact):
                        impact = None
                else:
                    qrel = None
        if impact is not None and len(valid_impacts) >= TRAILING_WINDOW:
            p90 = percentile(valid_impacts[-TRAILING_WINDOW:], D7_PCTL)
            state = bool(impact > p90)
        if rv_ok and len(valid_rvs) >= TRAILING_WINDOW:
            bucket = rv_bucket_from_trailing(hour.ret_abs_1h, valid_rvs[-TRAILING_WINDOW:])
        states.append(
            D7HourState(
                hour=hour,
                qrel_1h=qrel,
                impact_proxy=impact,
                d7_state=state,
                rv_bucket=bucket,
            )
        )
        if vol_ok:
            valid_volumes.append(hour.quote_volume_1h)
        if impact is not None:
            valid_impacts.append(impact)
        if rv_ok:
            valid_rvs.append(hour.ret_abs_1h)
    return states


def d7_index_by_hour_start(states: Sequence[D7HourState]) -> dict[int, int]:
    return {row.hour.hour_start_ms: i for i, row in enumerate(states)}


def d7_feasibility_census(states: Sequence[D7HourState]) -> dict[str, Any]:
    """Selector/support census. Does not compute t+1 scientific association."""

    by_start = d7_index_by_hour_start(states)
    constructed = len(states)
    valid_impact = 0
    state_n = 0
    state_by_year: dict[str, int] = {str(year): 0 for year in CONTROL_YEARS}
    state_by_year_bucket: dict[str, int] = {}
    target_eligible_n = 0
    target_eligible_by_year_bucket: dict[str, int] = {}
    candidate_by_year_bucket: dict[str, int] = {}
    selector_rows: list[tuple[int, int, int]] = []
    support_failures: list[str] = []

    def key(year: int, bucket: int) -> str:
        return f"{year}:{bucket}"

    for i, row in enumerate(states):
        if row.impact_proxy is not None:
            valid_impact += 1
        next_start = row.hour.hour_start_ms + HOUR_MS
        next_idx = by_start.get(next_start)
        next_valid_state = (
            next_idx is not None
            and next_start < PROTECTED_START_MS
            and states[next_idx].d7_state is not None
        )
        if next_valid_state:
            target_eligible_n += 1
            if row.rv_bucket is not None:
                tkey = key(row.hour.year, row.rv_bucket)
                target_eligible_by_year_bucket[tkey] = (
                    target_eligible_by_year_bucket.get(tkey, 0) + 1
                )
        if row.d7_state is True:
            state_n += 1
            state_by_year[str(row.hour.year)] = state_by_year.get(str(row.hour.year), 0) + 1
            if row.rv_bucket is not None:
                skey = key(row.hour.year, row.rv_bucket)
                state_by_year_bucket[skey] = state_by_year_bucket.get(skey, 0) + 1
            if next_valid_state and row.rv_bucket is not None:
                ckey = key(row.hour.year, row.rv_bucket)
                candidate_by_year_bucket[ckey] = candidate_by_year_bucket.get(ckey, 0) + 1
                selector_rows.append(
                    (row.hour.hour_start_ms, row.hour.year, int(row.rv_bucket))
                )

    if state_n < MIN_D7_STATE_TOTAL:
        support_failures.append(f"MIN_D7_STATE_TOTAL:{state_n}<{MIN_D7_STATE_TOTAL}")
    for year in CONTROL_YEARS:
        n_year = int(state_by_year.get(str(year), 0))
        if n_year < MIN_D7_STATE_PER_YEAR:
            support_failures.append(
                f"MIN_D7_STATE_PER_YEAR:{year}:{n_year}<{MIN_D7_STATE_PER_YEAR}"
            )
    for ckey, k in candidate_by_year_bucket.items():
        pool = int(target_eligible_by_year_bucket.get(ckey, 0))
        if pool < 2 * int(k):
            support_failures.append(
                f"STRATUM_POOL:{ckey}:K={k}:POOL={pool}<{2 * int(k)}"
            )

    status = (
        "DEFERRED_INSUFFICIENT_SELECTOR_SUPPORT"
        if support_failures
        else "OUTCOME_BLIND_READY"
    )
    return {
        "CONSTRUCTED_HOURS": constructed,
        "VALID_IMPACT_ROWS": valid_impact,
        "TARGET_ELIGIBLE_ROWS": target_eligible_n,
        "STATE_N": state_n,
        "STATE_BY_YEAR": {str(k): int(v) for k, v in sorted(state_by_year.items())},
        "STATE_BY_YEAR_RV_BUCKET": {
            str(k): int(v) for k, v in sorted(state_by_year_bucket.items())
        },
        "TARGET_ELIGIBLE_BY_YEAR_RV_BUCKET": {
            str(k): int(v) for k, v in sorted(target_eligible_by_year_bucket.items())
        },
        "CANDIDATE_BY_YEAR_RV_BUCKET": {
            str(k): int(v) for k, v in sorted(candidate_by_year_bucket.items())
        },
        "SELECTOR_N": len(selector_rows),
        "SELECTOR_DIGEST": d7_selector_digest(selector_rows),
        "SUPPORT_FAILURES": support_failures,
        "FEASIBILITY_STATUS": status,
        "D7_IMPLEMENTATION_STATUS": status,
        "MIN_D7_STATE_TOTAL": MIN_D7_STATE_TOTAL,
        "MIN_D7_STATE_PER_YEAR": MIN_D7_STATE_PER_YEAR,
        "SCIENTIFIC_T_PLUS_1_ASSOCIATION_COMPUTED": False,
        "SCIENTIFIC_OUTCOMES_COMPUTED": False,
    }


def d7_random_generator(seed: int = D7_SEED) -> np.random.Generator:
    return np.random.Generator(np.random.PCG64(int(seed)))


def d8_random_generator(seed: int = D8_SEED) -> np.random.Generator:
    return np.random.Generator(np.random.PCG64(int(seed)))


def year_rv_bucket_rate_matched_masks(
    years: Sequence[int],
    buckets: Sequence[int],
    target_eligible: Sequence[bool],
    candidate: Sequence[bool],
    *,
    seed: int = D7_SEED,
    n_replicates: int = N_RANDOM_CONTROLS,
) -> np.ndarray:
    n = len(years)
    if not (n == len(buckets) == len(target_eligible) == len(candidate)):
        raise Sprint02IntegrityError("D7_MASK_SHAPE")
    years_arr = np.asarray([int(year) for year in years], dtype=np.int64)
    bucket_arr = np.asarray([int(bucket) for bucket in buckets], dtype=np.int64)
    eligible = np.asarray(list(target_eligible), dtype=bool)
    cand = np.asarray(list(candidate), dtype=bool)
    if np.any(cand & ~eligible):
        raise Sprint02IntegrityError("D7_CANDIDATE_NOT_TARGET_ELIGIBLE")
    masks = np.zeros((int(n_replicates), n), dtype=bool)
    rng = d7_random_generator(seed)
    for year in CONTROL_YEARS:
        for bucket in range(N_RV_BUCKETS):
            in_stratum = (years_arr == int(year)) & (bucket_arr == int(bucket))
            k = int(np.count_nonzero(cand & in_stratum))
            pool = np.flatnonzero(eligible & in_stratum)
            if k == 0:
                continue
            if k > int(pool.size):
                raise Sprint02IntegrityError(
                    f"D7_K_EXCEEDS_POOL:{year}:{bucket}:{k}>{int(pool.size)}"
                )
            for replicate in range(int(n_replicates)):
                chosen = rng.choice(pool, size=k, replace=False)
                masks[replicate, chosen] = True
    return masks


def evaluate_d7_scientific(
    *,
    candidate: Sequence[bool],
    target: Sequence[float | bool],
    year: Sequence[int],
    rv_bucket: Sequence[int],
    target_eligible: Sequence[bool],
    integrity_ok: bool = True,
    seed: int = D7_SEED,
    n_replicates: int = N_RANDOM_CONTROLS,
) -> dict[str, Any]:
    """Pure scientific evaluator. Do not call on real CORE in this unit."""

    if not integrity_ok:
        return {
            "CLASSIFICATION": "D7_DISCOVERY_INVALID",
            "INTEGRITY_OK": False,
            "SCIENTIFIC_OUTCOMES_COMPUTED": True,
        }
    cand = np.asarray(list(candidate), dtype=bool)
    tgt = np.asarray(list(target), dtype=np.float64)
    years = [int(v) for v in year]
    buckets = [int(v) for v in rv_bucket]
    eligible = np.asarray(list(target_eligible), dtype=bool)
    if int(np.count_nonzero(cand)) == 0:
        return {
            "CLASSIFICATION": "D7_NO_USEFUL_STRUCTURE",
            "MU_D7_RULE": float("nan"),
            "STATISTICAL_GATE": False,
            "PRACTICAL_GATE": False,
            "TEMPORAL_GATE": False,
            "SCIENTIFIC_OUTCOMES_COMPUTED": True,
        }
    mu_rule = float(tgt[cand].mean())
    masks = year_rv_bucket_rate_matched_masks(
        years, buckets, eligible, cand, seed=seed, n_replicates=n_replicates
    )
    control_means = np.empty(int(n_replicates), dtype=np.float64)
    for i, mask in enumerate(masks):
        control_means[i] = float(tgt[mask].mean())
    mu_control = float(control_means.mean())
    delta = mu_rule - mu_control
    control_p95 = float(np.percentile(control_means, 95.0, method=PERCENTILE_METHOD))
    mc_p = (1.0 + float(np.count_nonzero(control_means >= mu_rule))) / (
        float(n_replicates) + 1.0
    )
    statistical = bool(mu_rule > control_p95)
    practical = bool(delta >= D7_PRACTICAL_GATE)
    yearly_positive = 0
    yearly: dict[str, float] = {}
    years_arr = np.asarray(years, dtype=np.int64)
    for y in CONTROL_YEARS:
        in_year = years_arr == int(y)
        cand_y = cand & in_year
        if not bool(cand_y.any()):
            yearly[str(y)] = float("nan")
            continue
        mu_rule_y = float(tgt[cand_y].mean())
        ctrl_y = np.empty(int(n_replicates), dtype=np.float64)
        for i, mask in enumerate(masks):
            selected = mask & in_year
            ctrl_y[i] = float(tgt[selected].mean()) if bool(selected.any()) else float("nan")
        delta_y = mu_rule_y - float(np.nanmean(ctrl_y))
        yearly[str(y)] = delta_y
        if delta_y > 0.0:
            yearly_positive += 1
    temporal = bool(yearly_positive >= D7_TEMPORAL_YEARS_REQUIRED)
    classification = (
        "D7_PROMISING_PROTOTYPE"
        if statistical and practical and temporal
        else "D7_NO_USEFUL_STRUCTURE"
    )
    return {
        "CLASSIFICATION": classification,
        "MU_D7_RULE": mu_rule,
        "MU_D7_CONTROL": mu_control,
        "DELTA_D7": delta,
        "CONTROL_D7_P95": control_p95,
        "MC_P_D7": mc_p,
        "STATISTICAL_GATE": statistical,
        "PRACTICAL_GATE": practical,
        "TEMPORAL_GATE": temporal,
        "YEARLY_DELTA_D7": yearly,
        "SCIENTIFIC_OUTCOMES_COMPUTED": True,
    }


def event_sign(event_return: float) -> int | None:
    if event_return > 0.0:
        return 1
    if event_return < 0.0:
        return -1
    return None


def build_d8_raw_candidates(hours: Sequence[HourBar]) -> list[D8RawCandidate]:
    out: list[D8RawCandidate] = []
    valid_abs: list[float] = []
    valid_vol: list[float] = []
    for hour in hours:
        abs_ret = abs(hour.event_return)
        vol = hour.quote_volume_1h
        abs_ok = math.isfinite(abs_ret)
        vol_ok = math.isfinite(vol)
        is_return_shock = False
        is_event = False
        is_control = False
        p99 = float("nan")
        p90 = float("nan")
        sign = event_sign(hour.event_return)
        if abs_ok and vol_ok and sign is not None:
            if len(valid_abs) >= TRAILING_WINDOW and len(valid_vol) >= TRAILING_WINDOW:
                p99 = percentile(valid_abs[-TRAILING_WINDOW:], D8_RETURN_PCTL)
                p90 = percentile(valid_vol[-TRAILING_WINDOW:], D8_VOLUME_PCTL)
                is_return_shock = bool(abs_ret > p99)
                is_event = bool(is_return_shock and vol > p90)
                is_control = bool(is_return_shock and vol <= p90)
        if abs_ok:
            valid_abs.append(abs_ret)
        if vol_ok:
            valid_vol.append(vol)
        if is_return_shock or is_event or is_control:
            out.append(
                D8RawCandidate(
                    hour=hour,
                    abs_event_return=abs_ret,
                    event_sign=int(sign or 0),
                    event_volume=vol,
                    p99_return=p99,
                    p90_volume=p90,
                    is_event=is_event,
                    is_control=is_control,
                    is_return_shock=is_return_shock,
                )
            )
    return out


def apply_6h_refractory(candidates: Sequence[D8RawCandidate]) -> list[D8RawCandidate]:
    kept: list[D8RawCandidate] = []
    last_start: int | None = None
    for row in sorted(candidates, key=lambda item: item.hour.hour_start_ms):
        start = row.hour.hour_start_ms
        if last_start is None or start >= last_start + EVENT_GAP_MS:
            kept.append(row)
            last_start = start
    return kept


def recovery_interval(hour_start_ms: int) -> tuple[int, int]:
    decision = hour_start_ms + HOUR_MS
    return decision, decision + RECOVERY_6H_MS


def intervals_overlap_positive(a: tuple[int, int], b: tuple[int, int]) -> bool:
    start = max(a[0], b[0])
    end = min(a[1], b[1])
    return end > start


def primary_recovery_legal(event_decision_t_ms: int) -> bool:
    return int(event_decision_t_ms) + RECOVERY_6H_MS < PROTECTED_START_MS


def diagnostic_24h_legal(event_decision_t_ms: int) -> bool:
    return int(event_decision_t_ms) + RECOVERY_24H_MS < PROTECTED_START_MS


def exclude_overlapping_controls(
    events: Sequence[D8RawCandidate],
    controls: Sequence[D8RawCandidate],
) -> list[D8RawCandidate]:
    event_intervals = [recovery_interval(row.hour.hour_start_ms) for row in events]
    kept: list[D8RawCandidate] = []
    for control in controls:
        interval = recovery_interval(control.hour.hour_start_ms)
        if any(intervals_overlap_positive(interval, other) for other in event_intervals):
            continue
        kept.append(control)
    return kept


def match_events_to_controls(
    events: Sequence[D8RawCandidate],
    controls: Sequence[D8RawCandidate],
) -> tuple[list[tuple[D8RawCandidate, D8RawCandidate, float]], list[str]]:
    unused = list(controls)
    pairs: list[tuple[D8RawCandidate, D8RawCandidate, float]] = []
    failures: list[str] = []
    ordered_events = sorted(
        events,
        key=lambda row: (-row.abs_event_return, row.hour.available_at_ms),
    )
    for event in ordered_events:
        eligible = [
            control
            for control in unused
            if control.hour.year == event.hour.year
            and control.event_sign == event.event_sign
        ]
        if not eligible:
            failures.append(
                f"UNMATCHED:{event.hour.hour_start_ms}:{event.hour.year}:{event.event_sign}"
            )
            continue
        best = min(
            eligible,
            key=lambda control: (
                abs(event.abs_event_return - control.abs_event_return),
                control.hour.available_at_ms,
            ),
        )
        distance = abs(event.abs_event_return - best.abs_event_return)
        pairs.append((event, best, distance))
        unused.remove(best)
    return pairs, failures


def _summarize_abs(rows: Sequence[D8RawCandidate]) -> dict[str, float | int]:
    if not rows:
        return {"N": 0}
    values = [row.abs_event_return for row in rows]
    return {
        "N": len(values),
        "MIN": float(min(values)),
        "P10": percentile(values, 10.0) if len(values) >= 2 else float(values[0]),
        "MEDIAN": median(values),
        "P90": percentile(values, 90.0) if len(values) >= 2 else float(values[0]),
        "MAX": float(max(values)),
    }


def d8_feasibility_census(hours: Sequence[HourBar]) -> dict[str, Any]:
    raw = build_d8_raw_candidates(hours)
    raw_return_shock = [row for row in raw if row.is_return_shock]
    raw_events = [row for row in raw if row.is_event]
    raw_controls = [row for row in raw if row.is_control]
    retained_events_all = apply_6h_refractory(raw_events)
    retained_controls_all = apply_6h_refractory(raw_controls)
    scientific_events = [
        row
        for row in retained_events_all
        if primary_recovery_legal(row.hour.available_at_ms)
    ]
    scientific_controls = [
        row
        for row in retained_controls_all
        if primary_recovery_legal(row.hour.available_at_ms)
    ]
    nonoverlap_controls = exclude_overlapping_controls(
        scientific_events, scientific_controls
    )
    pairs, match_failures = match_events_to_controls(
        scientific_events, nonoverlap_controls
    )

    events_by_year: dict[str, int] = {str(year): 0 for year in CONTROL_YEARS}
    events_by_year_sign: dict[str, int] = {}
    for row in scientific_events:
        events_by_year[str(row.hour.year)] = events_by_year.get(str(row.hour.year), 0) + 1
        key = f"{row.hour.year}:{row.event_sign}"
        events_by_year_sign[key] = events_by_year_sign.get(key, 0) + 1
    controls_by_year_sign: dict[str, int] = {}
    for row in nonoverlap_controls:
        key = f"{row.hour.year}:{row.event_sign}"
        controls_by_year_sign[key] = controls_by_year_sign.get(key, 0) + 1

    years_with_events = [year for year in CONTROL_YEARS if events_by_year.get(str(year), 0) > 0]
    years_with_at_least_three = [
        year for year in CONTROL_YEARS if events_by_year.get(str(year), 0) >= MIN_EVENTS_PER_YEAR_IN_AT_LEAST_TWO_YEARS
    ]
    event_failures: list[str] = []
    if len(scientific_events) < MIN_NONOVERLAPPING_EVENTS:
        event_failures.append(
            f"MIN_NONOVERLAPPING_EVENTS:{len(scientific_events)}<{MIN_NONOVERLAPPING_EVENTS}"
        )
    if len(years_with_events) < MIN_YEARS_WITH_EVENTS:
        event_failures.append(
            f"MIN_YEARS_WITH_EVENTS:{len(years_with_events)}<{MIN_YEARS_WITH_EVENTS}"
        )
    if len(years_with_at_least_three) < 2:
        event_failures.append(
            "MIN_EVENTS_PER_YEAR_IN_AT_LEAST_TWO_YEARS:"
            f"{len(years_with_at_least_three)}<2"
        )
    control_failures = list(match_failures)
    for key, n_event in events_by_year_sign.items():
        if n_event > 0 and int(controls_by_year_sign.get(key, 0)) <= 0:
            control_failures.append(f"STRATUM_NO_CONTROLS:{key}")
    if len(pairs) != len(scientific_events):
        control_failures.append(
            f"UNMATCHED_EVENT_COUNT:{len(scientific_events) - len(pairs)}"
        )

    if event_failures:
        event_status = "DEFERRED_INSUFFICIENT_EVENT_SUPPORT"
    else:
        event_status = "EVENT_SUPPORT_OK"
    unmatched_n = len(scientific_events) - len(pairs)
    control_failure_summary = []
    stratum_failures = [item for item in control_failures if item.startswith("STRATUM_NO_CONTROLS:")]
    control_failure_summary.extend(stratum_failures)
    if unmatched_n:
        control_failure_summary.append(f"UNMATCHED_EVENT_COUNT:{unmatched_n}")
    if control_failure_summary:
        control_status = "DEFERRED_INSUFFICIENT_CONTROL_SUPPORT"
    else:
        control_status = "CONTROL_SUPPORT_OK"
    if event_failures:
        feasibility_status = "DEFERRED_INSUFFICIENT_EVENT_SUPPORT"
    elif control_failure_summary:
        feasibility_status = "DEFERRED_INSUFFICIENT_CONTROL_SUPPORT"
    else:
        feasibility_status = "OUTCOME_BLIND_READY"

    distances = [distance for _, _, distance in pairs]
    return {
        "RAW_RETURN_SHOCK_N": len(raw_return_shock),
        "RAW_EVENT_N": len(raw_events),
        "RETAINED_EVENT_N": len(retained_events_all),
        "PROTECTED_WINDOW_ELIGIBLE_EVENT_N": len(scientific_events),
        "EVENT_BY_YEAR": {str(k): int(v) for k, v in sorted(events_by_year.items())},
        "EVENT_BY_YEAR_SIGN": {
            str(k): int(v) for k, v in sorted(events_by_year_sign.items())
        },
        "RAW_CONTROL_N": len(raw_controls),
        "RETAINED_CONTROL_N": len(retained_controls_all),
        "NONOVERLAP_CONTROL_N": len(nonoverlap_controls),
        "CONTROL_BY_YEAR_SIGN": {
            str(k): int(v) for k, v in sorted(controls_by_year_sign.items())
        },
        "MATCHED_PAIR_N": len(pairs),
        "EVENT_ABS_EVENT_RETURN_SUMMARY": _summarize_abs(scientific_events),
        "CONTROL_ABS_EVENT_RETURN_SUMMARY": _summarize_abs(nonoverlap_controls),
        "MATCHING_DISTANCE_SUMMARY": {
            "N": len(distances),
            "MIN": float(min(distances)) if distances else None,
            "MEDIAN": median(distances) if distances else None,
            "MAX": float(max(distances)) if distances else None,
        },
        "EVENT_SUPPORT_STATUS": event_status,
        "CONTROL_SUPPORT_STATUS": control_status,
        "EVENT_SUPPORT_FAILURES": event_failures,
        "CONTROL_SUPPORT_FAILURES": control_failure_summary,
        "UNMATCHED_EVENT_N": unmatched_n,
        "FEASIBILITY_STATUS": feasibility_status,
        "D8_IMPLEMENTATION_STATUS": feasibility_status,
        "RECOVERY_6H_COMPUTED": False,
        "RECOVERY_24H_COMPUTED": False,
        "SCIENTIFIC_OUTCOMES_COMPUTED": False,
    }


def lookup_close_at_available_at(
    closes: Mapping[int, float],
    available_at_ms: int,
) -> float:
    if int(available_at_ms) not in closes:
        raise Sprint02IntegrityError(f"MISSING_CLOSE_AT:{available_at_ms}")
    return float(closes[int(available_at_ms)])


def recovery_6h(
    event_return: float,
    event_close: float,
    price_t_plus_6h: float,
) -> float:
    if not math.isfinite(event_return) or event_return == 0.0:
        raise Sprint02IntegrityError("EVENT_RETURN_INELIGIBLE")
    if event_close <= 0.0 or price_t_plus_6h <= 0.0:
        raise Sprint02IntegrityError("RECOVERY_PRICE_NONPOSITIVE")
    sign = 1.0 if event_return > 0.0 else -1.0
    return float(
        -sign * math.log(price_t_plus_6h / event_close) / abs(event_return)
    )


def evaluate_d8_scientific(
    pair_deltas: Sequence[float],
    pair_years: Sequence[int],
    *,
    integrity_ok: bool = True,
    event_support_ok: bool = True,
    control_support_ok: bool = True,
    seed: int = D8_SEED,
    n_randomizations: int = N_RANDOMIZATIONS,
) -> dict[str, Any]:
    """Pure scientific evaluator. Do not call on real CORE in this unit."""

    if not integrity_ok:
        return {
            "CLASSIFICATION": "D8_DISCOVERY_INVALID",
            "INTEGRITY_OK": False,
            "SCIENTIFIC_OUTCOMES_COMPUTED": True,
        }
    if not event_support_ok:
        return {
            "CLASSIFICATION": "DEFERRED_INSUFFICIENT_EVENT_SUPPORT",
            "SCIENTIFIC_OUTCOMES_COMPUTED": False,
        }
    if not control_support_ok:
        return {
            "CLASSIFICATION": "DEFERRED_INSUFFICIENT_CONTROL_SUPPORT",
            "SCIENTIFIC_OUTCOMES_COMPUTED": False,
        }
    deltas = np.asarray(list(pair_deltas), dtype=np.float64)
    years = np.asarray([int(year) for year in pair_years], dtype=np.int64)
    if deltas.size == 0:
        return {
            "CLASSIFICATION": "DEFERRED_INSUFFICIENT_EVENT_SUPPORT",
            "SCIENTIFIC_OUTCOMES_COMPUTED": False,
        }
    observed = float(deltas.mean())
    rng = d8_random_generator(seed)
    count_ge = 0
    for _ in range(int(n_randomizations)):
        signs = rng.choice(np.array([-1.0, 1.0], dtype=np.float64), size=deltas.size)
        if float((deltas * signs).mean()) >= observed:
            count_ge += 1
    mc_p = (1.0 + float(count_ge)) / (float(n_randomizations) + 1.0)
    statistical = bool(mc_p <= D8_MC_ALPHA and observed > 0.0)
    practical = bool(observed >= D8_PRACTICAL_GATE)
    supported_years = 0
    yearly: dict[str, float] = {}
    for year in CONTROL_YEARS:
        mask = years == int(year)
        n = int(np.count_nonzero(mask))
        if n < D8_TEMPORAL_MIN_PAIRS:
            yearly[str(year)] = float("nan")
            continue
        mean_y = float(deltas[mask].mean())
        yearly[str(year)] = mean_y
        if mean_y > 0.0:
            supported_years += 1
    temporal = bool(supported_years >= D8_TEMPORAL_YEARS_REQUIRED)
    classification = (
        "D8_PROMISING_PROTOTYPE"
        if statistical and practical and temporal
        else "D8_NO_USEFUL_STRUCTURE"
    )
    return {
        "CLASSIFICATION": classification,
        "DELTA_RECOVERY_6H": observed,
        "MC_P_D8": mc_p,
        "STATISTICAL_GATE": statistical,
        "PRACTICAL_GATE": practical,
        "TEMPORAL_GATE": temporal,
        "YEARLY_PAIR_DELTA": yearly,
        "SCIENTIFIC_OUTCOMES_COMPUTED": True,
        "NEGATIVE_CONTINUATION_DOES_NOT_RESCUE": True,
    }


def d7_selector_digest(selector_rows: Sequence[tuple[int, int, int]]) -> str:
    digest_src = canonical_json(
        {
            "rows": [list(row) for row in selector_rows],
            "n": len(selector_rows),
        }
    )
    return sha256_bytes(digest_src.encode("utf-8"))


def assert_d7_selector_identity(census: Mapping[str, Any]) -> None:
    if census.get("SCIENTIFIC_T_PLUS_1_ASSOCIATION_COMPUTED") is True:
        raise RealScientificOutcomeForbidden("SELECTOR_IDENTITY_USED_TPLUS1")
    if census.get("SCIENTIFIC_OUTCOMES_COMPUTED") is True:
        raise RealScientificOutcomeForbidden("SELECTOR_IDENTITY_USED_OUTCOMES")
    checks = (
        ("SELECTOR_N", D7_SELECTOR_N),
        ("SELECTOR_DIGEST", D7_SELECTOR_DIGEST),
        ("CONSTRUCTED_HOURS", D7_CONSTRUCTED_HOURS),
        ("VALID_IMPACT_ROWS", D7_VALID_IMPACT_ROWS),
        ("TARGET_ELIGIBLE_ROWS", D7_TARGET_ELIGIBLE_ROWS),
    )
    for key, expected in checks:
        got = census.get(key)
        if got != expected:
            raise SelectorIdentityError(f"D7_{key}_MISMATCH:{got}!={expected}")


def recompute_d7_selector_identity(states: Sequence[D7HourState]) -> dict[str, Any]:
    """Rebuild frozen D7 selector identity from states. No t+1 outcomes."""

    census = d7_feasibility_census(states)
    if census.get("SCIENTIFIC_T_PLUS_1_ASSOCIATION_COMPUTED") is not False:
        raise RealScientificOutcomeForbidden("SELECTOR_RECOMPUTE_COMPUTED_TPLUS1")
    if census.get("SCIENTIFIC_OUTCOMES_COMPUTED") is not False:
        raise RealScientificOutcomeForbidden("SELECTOR_RECOMPUTE_COMPUTED_OUTCOMES")
    assert_d7_selector_identity(census)
    return {
        "SELECTOR_N": census["SELECTOR_N"],
        "SELECTOR_DIGEST": census["SELECTOR_DIGEST"],
        "CONSTRUCTED_HOURS": census["CONSTRUCTED_HOURS"],
        "VALID_IMPACT_ROWS": census["VALID_IMPACT_ROWS"],
        "TARGET_ELIGIBLE_ROWS": census["TARGET_ELIGIBLE_ROWS"],
        "SCIENTIFIC_T_PLUS_1_ASSOCIATION_COMPUTED": False,
        "SCIENTIFIC_OUTCOMES_COMPUTED": False,
    }


def assert_d8_deferred_final(census: Mapping[str, Any]) -> None:
    if census.get("RECOVERY_6H_COMPUTED") is True or census.get("RECOVERY_24H_COMPUTED") is True:
        raise RealScientificOutcomeForbidden("D8_RECOVERY_COMPUTED")
    if census.get("SCIENTIFIC_OUTCOMES_COMPUTED") is True:
        raise RealScientificOutcomeForbidden("D8_SCIENTIFIC_OUTCOMES_COMPUTED")
    if census.get("FEASIBILITY_STATUS") == "D8_NO_USEFUL_STRUCTURE":
        raise Sprint02IntegrityError("D8_MUST_NOT_BE_NO_USEFUL_STRUCTURE")
    if census.get("FEASIBILITY_STATUS") != D8_STATUS:
        raise Sprint02IntegrityError(
            f"D8_STATUS_MISMATCH:{census.get('FEASIBILITY_STATUS')}!={D8_STATUS}"
        )
    expected = {
        "RAW_RETURN_SHOCK_N": FROZEN_D8_RAW_RETURN_SHOCK_N,
        "RAW_EVENT_N": FROZEN_D8_RAW_EVENT_N,
        "RETAINED_EVENT_N": FROZEN_D8_RETAINED_EVENT_N,
        "RAW_CONTROL_N": FROZEN_D8_RAW_CONTROL_N,
        "RETAINED_CONTROL_N": FROZEN_D8_RETAINED_CONTROL_N,
        "MATCHED_PAIR_N": FROZEN_D8_MATCHED_PAIR_N,
        "UNMATCHED_EVENT_N": FROZEN_D8_UNMATCHED_EVENT_N,
    }
    for key, value in expected.items():
        got = census.get(key)
        if got != value:
            raise Sprint02IntegrityError(f"D8_{key}_MISMATCH:{got}!={value}")
    if D8_SCIENTIFIC_EXECUTION_ELIGIBLE is not False:
        raise Sprint02IntegrityError("D8_MUST_REMAIN_NON_EXECUTABLE")
    if D8_SCIENTIFIC_RECOVERY_HYPOTHESIS_EVALUATED is not False:
        raise Sprint02IntegrityError("D8_RECOVERY_HYPOTHESIS_MUST_REMAIN_UNEVALUATED")


def implementation_review_status(
    *,
    data_identity_mode: str,
    full_monthly_exact_byte_verification: bool,
    d7_selector_frozen: bool,
    d8_scientific_execution_eligible: bool,
    scientific_outcomes_computed: bool,
    protected_2025_opened: bool,
    protected_2026_opened: bool,
) -> str:
    if (
        data_identity_mode == DATA_IDENTITY_MODE
        and full_monthly_exact_byte_verification is True
        and d7_selector_frozen is True
        and d8_scientific_execution_eligible is False
        and scientific_outcomes_computed is False
        and protected_2025_opened is False
        and protected_2026_opened is False
    ):
        return "PASS"
    return "FAIL"


def feasibility_artifact_sha256(payload: Mapping[str, Any]) -> str:
    body = {
        key: value
        for key, value in payload.items()
        if key
        not in ("RUN_IDENTITY", "AUTHORITY_BINDINGS", "FEASIBILITY_ARTIFACT_SHA256")
    }
    return sha256_bytes(canonical_json(body).encode("utf-8"))


def assert_no_scientific_calls_in_feasibility_source(source: str) -> None:
    forbidden = (
        "evaluate_d7_scientific(",
        "evaluate_d8_scientific(",
        "recovery_6h(",
        "lookup_close_at_available_at(",
    )
    for token in forbidden:
        if token in source:
            raise RealScientificOutcomeForbidden(f"FEASIBILITY_CALLS_SCIENTIFIC:{token}")


def run_identity_payload(bindings: Mapping[str, Any]) -> str:
    return sha256_bytes(canonical_json(dict(bindings)).encode("utf-8"))
