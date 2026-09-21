"""Shared Discovery Sprint 01 helpers.

Fail-closed 2025/2026 partition refusal, frozen snapshot binding, and
reuse of MARKET-06 evaluator mathematics without confirmatory lifecycle
machinery.
"""

from __future__ import annotations

import hashlib
import io
import json
import math
import re
import zipfile
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np

from scripts.research.market_06_cross_venue_dislocation_authority import (
    Market06IncompleteExecution,
    Market06RowIneligible,
)
from scripts.research.market_06_cross_venue_dislocation_evaluator import (
    FUTURE_BARS,
    REFERENCE_COUNT,
    RV_RETURN_COUNT,
    arithmetic_mae,
    btc_ret_24h,
    btc_side_from_ret,
    dislocation_d,
    feature_cutoff_ms,
    get_perp_bar_ending_at,
    get_perp_bar_opening_at,
    is_forbidden_decision,
    robust_dislocation_z,
    rv_btc_24h,
)
from scripts.research.market_06_cross_venue_dislocation_parsers import (
    BAR_MS,
    OKX_CONFIRM,
    OKX_ROW_WIDTH,
    PerpBar,
    parse_binance_klines_csv,
)


UTC = timezone.utc

CORE_BTC_DATASET_ID = "CORE_BTC_BINANCE_V0"
CORE_BTC_SNAPSHOT = "717d37a404f81eefd58c9a796cc11868c48226baf1de8ffecad5e5607f8dd415"
CORE_ETH_DATASET_ID = "CORE_ETH_BINANCE_V0"
CORE_ETH_SNAPSHOT = "4b9c113f659e1c1ca71498096dfdc2628a1016346aed40e19020efb64c85ad15"
M06_DATASET_ID = "MARKET_06_OKX_BINANCE_FEASIBILITY_V0"
M06_SNAPSHOT = "e0403e40a9b1e2903f15fb9283ec6caf54788e48153038982e364d4318183e68"

CORE_BTC_ROOT_REL = "artifacts/research_data/CORE_BTC_BINANCE_V0"
CORE_ETH_ROOT_REL = "artifacts/research_data/CORE_ETH_BINANCE_V0"
CORE_BTC_SNAPSHOT_DOC_REL = "docs/research_data/CORE_BTC_BINANCE_V0/SNAPSHOT_717d37a4.json"
CORE_ETH_SNAPSHOT_DOC_REL = "docs/research_data/CORE_ETH_BINANCE_V0/SNAPSHOT_4b9c113f.json"
M06_DURABLE_REL = "docs/research_data/MARKET_06_OKX_BINANCE_FEASIBILITY_V0/durable_raw"
M06_SNAPSHOT_DOC_REL = "docs/research_data/MARKET_06_OKX_BINANCE_FEASIBILITY_V0/snapshot.json"

SPEC_AUTHORITY = (
    "docs/research/DISCOVERY_SPRINT_01_SPEC_COMPILATION.{json,md} "
    "superseded in place by DISCOVERY_SPRINT_01_RED_TEAM_REVIEW, "
    "DISCOVERY_SPRINT_01_PRE_EXECUTION_CORRECTION_D3_D4, and "
    "DISCOVERY_SPRINT_01_MECHANICAL_PRE_EXECUTION_FIX (latest explicit "
    "correction blocks are authority)"
)

PROTECTED_START = datetime(2025, 1, 1, tzinfo=UTC)
PROTECTED_START_MS = int(PROTECTED_START.timestamp() * 1000)
DISCOVERY_END = PROTECTED_START

RULE1_INTERVAL_START = datetime(2020, 2, 1, 0, 5, tzinfo=UTC)
RULE2_INTERVAL_START = datetime(2022, 2, 1, 0, 5, tzinfo=UTC)
D3_INTERVAL_START = datetime(2020, 2, 1, 0, 5, tzinfo=UTC)
D4_INTERVAL_START = datetime(2020, 2, 1, 0, 5, tzinfo=UTC)
D5_INTERVAL_START = datetime(2022, 2, 1, 0, 5, tzinfo=UTC)

D2_RANDOM_CONTROL_SEED = 20260921102
D3_NULL_SURROGATE_SEED = 20260921103
D4_NULL_SEED = 20260921104
D5_RANDOM_CONTROL_SEED = 20260921105

RV_TRAILING_WINDOW = 250
RV_PCTL = 90.0
DISLOCATION_Z_THRESHOLD = 2.0
D4_ROLLING_WINDOW = 90
D4_BLOCK_LENGTH = 20
D4_PRACTICAL_GATE = 0.15
N_REPLICATES = 1000
D3_BLOCK_LENGTH = 12
D3_COMPANION_BLOCKS = (6, 24)

LEGAL_MONTHS = tuple(
    f"{year:04d}-{month:02d}" for year in range(2020, 2025) for month in range(1, 13)
)

_PROTECTED_PERIOD_RE = re.compile(r"(?:^|[^0-9])(2025|2026)-\d{2}")


class ProtectedYearRefused(RuntimeError):
    """Opening a 2025/2026 partition or timestamp was refused."""


class MissingLocalData(RuntimeError):
    """Required frozen local snapshot material is absent."""


class SnapshotIdentityError(RuntimeError):
    """Opened files do not match the frozen snapshot identity."""


class DeferredFunctionalError(RuntimeError):
    """A Sprint-01-deferred functional was requested."""


@dataclass(frozen=True)
class DiscoveryRow:
    t_ms: int
    year: int
    rv: float
    ret: float
    side: float
    severity: float
    entry_open: float
    future_closes: tuple[float, ...]
    z: float | None = None


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
    return Path(__file__).resolve().parents[3]


def utc_from_ms(t_ms: int) -> datetime:
    return datetime.fromtimestamp(t_ms / 1000.0, tz=UTC)


def ms_from_utc(moment: datetime) -> int:
    if moment.tzinfo is None:
        raise ValueError("NAIVE_DATETIME")
    return int(moment.timestamp() * 1000)


def path_is_protected_partition(path: Path) -> bool:
    for part in path.parts:
        if _PROTECTED_PERIOD_RE.search(part):
            return True
        if part.startswith("2025-") or part.startswith("2026-"):
            return True
    name = path.name.lower()
    if name in {"bars.parquet", "bars.csv"} and any(
        token in str(path) for token in ("/5m/", "/15m/", "/1h/", "/1m/daily/")
    ):
        # Unpartitioned HTF/daily files in CORE snapshots span protected years.
        return True
    return False


def assert_openable(path: Path) -> None:
    if path_is_protected_partition(path):
        raise ProtectedYearRefused(f"PROTECTED_PARTITION_REFUSED:{path}")


def open_bytes(path: Path, log: OpenedFileLog, *, repo_root_path: Path) -> bytes:
    assert_openable(path)
    data = path.read_bytes()
    log.record(path, repo_root=repo_root_path)
    return data


def open_text(path: Path, log: OpenedFileLog, *, repo_root_path: Path) -> str:
    return open_bytes(path, log, repo_root_path=repo_root_path).decode("utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(v) for v in value]
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, (np.integer, int)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        number = float(value)
        if not math.isfinite(number):
            return None
        return number
    if isinstance(value, datetime):
        return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    if value is None:
        return None
    return value


def write_result_pair(
    payload: Mapping[str, Any],
    json_path: Path,
    md_path: Path,
    *,
    title: str,
) -> None:
    json_path.parent.mkdir(parents=True, exist_ok=True)
    dumped = jsonable(dict(payload))
    json_path.write_text(json.dumps(dumped, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lines = [f"# {title}", "", "Adaptive discovery result. Not confirmatory.", ""]
    for key in (
        "DISCOVERY_ID",
        "TERMINAL_CLASSIFICATION",
        "SPEC_AUTHORITY",
        "IMPLEMENTATION_COMMIT",
        "INTERVAL_USED",
        "DATASET_IDENTITIES",
        "SEEDS",
        "ROW_COUNTS",
        "YEAR_BREAKDOWN",
        "PRIMARY_METRICS",
        "BASELINE_METRICS",
        "PROTOTYPE_GATE_FIELDS",
        "SEARCH_SURFACE_ATTEMPTED",
        "FILES_OPENED",
        "KNOWN_LIMITATIONS",
        "PROTECTED_2025_OPENED",
        "PROTECTED_2026_OPENED",
    ):
        if key in dumped:
            lines.append(f"## {key}")
            lines.append("")
            lines.append("```json")
            lines.append(json.dumps(dumped[key], indent=2, sort_keys=True))
            lines.append("```")
            lines.append("")
    md_path.write_text("\n".join(lines), encoding="utf-8")


def blocked_result(
    *,
    discovery_id: str,
    implementation_commit: str,
    missing: Sequence[str],
    interval: Mapping[str, str],
    seeds: Mapping[str, int],
    search_surface: Sequence[str],
    files_opened: Sequence[str],
    extra: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "DISCOVERY_ID": discovery_id,
        "SPEC_AUTHORITY": SPEC_AUTHORITY,
        "IMPLEMENTATION_COMMIT": implementation_commit,
        "DATASET_IDENTITIES": {
            CORE_BTC_DATASET_ID: CORE_BTC_SNAPSHOT,
            CORE_ETH_DATASET_ID: CORE_ETH_SNAPSHOT,
            M06_DATASET_ID: M06_SNAPSHOT,
        },
        "INTERVAL_USED": dict(interval),
        "FILES_OPENED": list(files_opened),
        "SEARCH_SURFACE_ATTEMPTED": list(search_surface),
        "SEEDS": dict(seeds),
        "ROW_COUNTS": {},
        "YEAR_BREAKDOWN": {},
        "PRIMARY_METRICS": {},
        "BASELINE_METRICS": {},
        "PROTOTYPE_GATE_FIELDS": {},
        "TERMINAL_CLASSIFICATION": "BLOCKED_MISSING_LOCAL_DATA",
        "KNOWN_LIMITATIONS": [
            "Required frozen local snapshot material was absent.",
            "No online substitution or new snapshot reconstruction was performed.",
            *[f"missing:{item}" for item in missing],
        ],
        "PROTECTED_2025_OPENED": False,
        "PROTECTED_2026_OPENED": False,
        "MISSING_LOCAL_DATA": list(missing),
    }
    if extra:
        payload.update(dict(extra))
    return payload


def iter_discovery_decision_times(start: datetime, end_exclusive: datetime) -> list[datetime]:
    if start.tzinfo is None or end_exclusive.tzinfo is None:
        raise ValueError("NAIVE_DATETIME")
    if end_exclusive > PROTECTED_START:
        raise ProtectedYearRefused("DISCOVERY_INTERVAL_MUST_END_BEFORE_2025")
    cursor = start.astimezone(UTC)
    if cursor.hour != 0 or cursor.minute != 5:
        cursor = datetime(cursor.year, cursor.month, cursor.day, 0, 5, tzinfo=UTC)
        if cursor < start.astimezone(UTC):
            cursor = cursor + timedelta(days=1)
    out: list[datetime] = []
    while cursor < end_exclusive:
        if cursor.year >= 2025:
            raise ProtectedYearRefused(f"PROTECTED_DECISION:{cursor.isoformat()}")
        if is_forbidden_decision(cursor) is None:
            out.append(cursor)
        cursor = cursor + timedelta(days=1)
    return out


def preflight_local_data(root: Path | None = None) -> dict[str, Any]:
    base = root or repo_root()
    btc_root = base / CORE_BTC_ROOT_REL
    eth_root = base / CORE_ETH_ROOT_REL
    m06_root = base / M06_DURABLE_REL
    btc_months = _existing_legal_monthly(btc_root)
    eth_months = _existing_legal_monthly(eth_root)
    binance_zips = []
    okx_pages = []
    if (m06_root / "binance").is_dir():
        for path in sorted((m06_root / "binance").iterdir()):
            if path.suffix.lower() == ".zip":
                if path_is_protected_partition(path):
                    continue
                binance_zips.append(path.name)
    if (m06_root / "okx").is_dir():
        okx_pages = [p.name for p in sorted((m06_root / "okx").iterdir()) if p.is_file()]
    return {
        "BTC_DATA_PRESENT": len(btc_months) == 60,
        "ETH_DATA_PRESENT": len(eth_months) == 60,
        "M06_CROSS_VENUE_DATA_PRESENT": len(binance_zips) == 36 and len(okx_pages) == 1053,
        "btc_month_count": len(btc_months),
        "eth_month_count": len(eth_months),
        "m06_binance_zip_count": len(binance_zips),
        "m06_okx_page_count": len(okx_pages),
        "btc_root": str(btc_root),
        "eth_root": str(eth_root),
        "m06_root": str(m06_root),
        "CORE_BTC_SNAPSHOT": CORE_BTC_SNAPSHOT,
        "CORE_ETH_SNAPSHOT": CORE_ETH_SNAPSHOT,
        "M06_SNAPSHOT": M06_SNAPSHOT,
    }


def _existing_legal_monthly(dataset_root: Path) -> list[str]:
    found: list[str] = []
    monthly = dataset_root / "canonical" / "1m" / "monthly"
    if not monthly.is_dir():
        return found
    for period in LEGAL_MONTHS:
        path = monthly / f"{period}.parquet"
        if path.is_file() and not path_is_protected_partition(path):
            found.append(period)
    return found


def load_core_5m_perp(
    *,
    dataset_id: str,
    snapshot_id: str,
    snapshot_doc_rel: str,
    root_rel: str,
    log: OpenedFileLog,
    repo: Path | None = None,
) -> dict[int, PerpBar]:
    base = repo or repo_root()
    root = base / root_rel
    if not root.is_dir():
        raise MissingLocalData(f"{dataset_id}:missing_root:{root}")
    snapshot_path = base / snapshot_doc_rel
    identity = json.loads(snapshot_path.read_text(encoding="utf-8"))
    payload = identity.get("identity_payload") or identity
    bound = payload.get("snapshot_id") or identity.get("snapshot_id")
    if bound != snapshot_id:
        raise SnapshotIdentityError(f"{dataset_id}:snapshot_mismatch:{bound}")
    checksums = payload.get("output_checksums") or {}
    monthly_dir = root / "canonical" / "1m" / "monthly"
    if not monthly_dir.is_dir():
        raise MissingLocalData(f"{dataset_id}:missing_monthly:{monthly_dir}")
    one_minute: list[tuple[int, float, float, float, float]] = []
    for period in LEGAL_MONTHS:
        path = monthly_dir / f"{period}.parquet"
        if not path.is_file():
            raise MissingLocalData(f"{dataset_id}:missing_month:{period}")
        assert_openable(path)
        raw = path.read_bytes()
        expected = checksums.get(f"canonical/1m/monthly/{period}.parquet")
        if expected is not None and sha256_bytes(raw) != expected:
            raise SnapshotIdentityError(f"{dataset_id}:checksum_mismatch:{period}")
        log.record(path, repo_root=base)
        rows = _read_parquet_ohlc(path)
        for open_ms, o, h, l, c in rows:
            if open_ms >= PROTECTED_START_MS:
                raise ProtectedYearRefused(f"{dataset_id}:protected_timestamp:{open_ms}")
            one_minute.append((open_ms, o, h, l, c))
    one_minute.sort(key=lambda row: row[0])
    return aggregate_1m_to_5m(one_minute)


def _read_parquet_ohlc(path: Path) -> list[tuple[int, float, float, float, float]]:
    import pyarrow.parquet as pq

    table = pq.read_table(path, columns=["open_time_ms", "open", "high", "low", "close"])
    opens = table.column("open_time_ms").to_pylist()
    o = table.column("open").to_pylist()
    h = table.column("high").to_pylist()
    l = table.column("low").to_pylist()
    c = table.column("close").to_pylist()
    out: list[tuple[int, float, float, float, float]] = []
    for i, open_ms in enumerate(opens):
        ts = int(open_ms)
        if ts >= PROTECTED_START_MS:
            raise ProtectedYearRefused(f"PROTECTED_TIMESTAMP:{path}:{ts}")
        out.append((ts, float(o[i]), float(h[i]), float(l[i]), float(c[i])))
    return out


def aggregate_1m_to_5m(
    rows: Sequence[tuple[int, float, float, float, float]],
) -> dict[int, PerpBar]:
    """Downsample complete 1m bars to 5m. Does not fabricate higher frequency."""

    by_time = {int(r[0]): r for r in rows}
    if not by_time:
        return {}
    step = 5 * 60_000
    start = min(by_time) - (min(by_time) % step)
    end = max(by_time) + 60_000
    out: dict[int, PerpBar] = {}
    bucket = start
    while bucket < end and bucket < PROTECTED_START_MS:
        members = []
        missing = False
        for k in range(5):
            row = by_time.get(bucket + k * 60_000)
            if row is None:
                missing = True
                break
            members.append(row)
        if not missing:
            out[bucket] = PerpBar(
                open_time_ms=bucket,
                open=float(members[0][1]),
                high=max(float(m[2]) for m in members),
                low=min(float(m[3]) for m in members),
                close=float(members[-1][4]),
            )
        bucket += step
    return out


def load_core_btc_5m(log: OpenedFileLog, *, repo: Path | None = None) -> dict[int, PerpBar]:
    return load_core_5m_perp(
        dataset_id=CORE_BTC_DATASET_ID,
        snapshot_id=CORE_BTC_SNAPSHOT,
        snapshot_doc_rel=CORE_BTC_SNAPSHOT_DOC_REL,
        root_rel=CORE_BTC_ROOT_REL,
        log=log,
        repo=repo,
    )


def load_core_eth_5m(log: OpenedFileLog, *, repo: Path | None = None) -> dict[int, PerpBar]:
    return load_core_5m_perp(
        dataset_id=CORE_ETH_DATASET_ID,
        snapshot_id=CORE_ETH_SNAPSHOT,
        snapshot_doc_rel=CORE_ETH_SNAPSHOT_DOC_REL,
        root_rel=CORE_ETH_ROOT_REL,
        log=log,
        repo=repo,
    )


def parse_okx_history_discovery(data: bytes, *, source: str) -> dict[int, float]:
    """Parse OKX history JSON without the MARKET-06 permit guard."""

    try:
        payload = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise Market06IncompleteExecution(f"OKX_JSON:{source}") from exc
    if str(payload.get("code")) != "0":
        raise Market06IncompleteExecution(f"OKX_CODE:{source}:{payload.get('code')}")
    rows = payload.get("data") or []
    if not isinstance(rows, list):
        raise Market06IncompleteExecution(f"OKX_DATA:{source}")
    closes: dict[int, float] = {}
    for row in rows:
        if not isinstance(row, list) or len(row) != OKX_ROW_WIDTH:
            raise Market06IncompleteExecution(f"OKX_SCHEMA:{source}")
        try:
            raw_ts = int(row[0])
        except (TypeError, ValueError) as exc:
            raise Market06IncompleteExecution(f"OKX_TIMESTAMP:{source}") from exc
        if raw_ts % BAR_MS != 0:
            raise Market06IncompleteExecution(f"NOT_5M_ALIGNED:{source}:{raw_ts}")
        if raw_ts >= PROTECTED_START_MS:
            raise ProtectedYearRefused(f"OKX_PROTECTED_TIMESTAMP:{source}:{raw_ts}")
        if str(row[8]) != OKX_CONFIRM:
            raise Market06IncompleteExecution(f"OKX_CONFIRM:{source}:{row[8]}")
        close_px = float(row[4])
        if not math.isfinite(close_px) or close_px <= 0.0:
            raise Market06IncompleteExecution(f"OKX_CLOSE:{source}")
        previous = closes.get(raw_ts)
        if previous is not None and previous != close_px:
            raise Market06IncompleteExecution(f"OKX_CONFLICT:{source}:{raw_ts}")
        closes[raw_ts] = close_px
    return closes


def load_m06_cross_venue(
    log: OpenedFileLog,
    *,
    repo: Path | None = None,
) -> tuple[dict[int, PerpBar], dict[int, float], str]:
    base = repo or repo_root()
    hashes_path = base / "docs/research_data/MARKET_06_OKX_BINANCE_FEASIBILITY_V0/HASHES.json"
    snapshot_doc = json.loads(hashes_path.read_text(encoding="utf-8"))
    bound = snapshot_doc.get("snapshot_id")
    if bound != M06_SNAPSHOT:
        raise SnapshotIdentityError(f"M06:snapshot_mismatch:{bound}")
    raw_root = base / M06_DURABLE_REL
    binance_dir = raw_root / "binance"
    okx_dir = raw_root / "okx"
    if not binance_dir.is_dir() or not okx_dir.is_dir():
        raise MissingLocalData("M06:missing_durable_raw")
    perp: dict[int, PerpBar] = {}
    zip_count = 0
    for path in sorted(binance_dir.iterdir()):
        if path.suffix.lower() != ".zip":
            continue
        assert_openable(path)
        data = path.read_bytes()
        log.record(path, repo_root=base)
        zip_count += 1
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            csv_members = [name for name in archive.namelist() if name.lower().endswith(".csv")]
            if len(csv_members) != 1:
                raise Market06IncompleteExecution(f"BINANCE_ZIP_MEMBERS:{path.name}")
            text = archive.read(csv_members[0]).decode("utf-8")
        for bar in parse_binance_klines_csv(text, source=path.name):
            if bar.open_time_ms >= PROTECTED_START_MS:
                raise ProtectedYearRefused(f"M06_PROTECTED_TIMESTAMP:{path.name}:{bar.open_time_ms}")
            existing = perp.get(bar.open_time_ms)
            if existing is not None and existing != bar:
                raise Market06IncompleteExecution(f"BINANCE_CONFLICT:{bar.open_time_ms}")
            perp[bar.open_time_ms] = bar
    if zip_count != 36:
        raise MissingLocalData(f"M06:binance_zip_count:{zip_count}")
    spot: dict[int, float] = {}
    page_count = 0
    for path in sorted(okx_dir.iterdir()):
        if not path.is_file():
            continue
        assert_openable(path)
        data = path.read_bytes()
        log.record(path, repo_root=base)
        page_count += 1
        parsed = parse_okx_history_discovery(data, source=path.name)
        for ts, close in parsed.items():
            previous = spot.get(ts)
            if previous is not None and previous != close:
                raise Market06IncompleteExecution(f"OKX_CONFLICT:{ts}")
            spot[ts] = close
    if page_count != 1053:
        raise MissingLocalData(f"M06:okx_page_count:{page_count}")
    return perp, spot, M06_SNAPSHOT


def precompute_d_ending(
    perp: Mapping[int, PerpBar], spot: Mapping[int, float]
) -> dict[int, float]:
    out: dict[int, float] = {}
    for open_ms, bar in perp.items():
        close_spot = spot.get(int(open_ms))
        if close_spot is None:
            continue
        boundary = int(open_ms) + BAR_MS
        if int(open_ms) >= PROTECTED_START_MS:
            raise ProtectedYearRefused(f"PROTECTED_D_OPEN:{open_ms}")
        if boundary >= PROTECTED_START_MS:
            # Bar opens in 2024 and ends on the exclusive 2025-01-01 boundary.
            # It is never a legal discovery input; skip rather than opening 2025.
            continue
        out[boundary] = dislocation_d(bar.close, close_spot)
    return out


def construct_discovery_row(
    t_ms: int,
    perp: Mapping[int, PerpBar],
    *,
    spot: Mapping[int, float] | None = None,
    require_z: bool = False,
    d_ending: Mapping[int, float] | None = None,
) -> DiscoveryRow | None:
    moment = utc_from_ms(t_ms)
    if moment.year >= 2025:
        raise ProtectedYearRefused(f"PROTECTED_DECISION:{moment.isoformat()}")
    if is_forbidden_decision(moment) is not None:
        return None
    e_ms = feature_cutoff_ms(t_ms)
    e_bar = get_perp_bar_ending_at(perp, e_ms)
    e_24h = get_perp_bar_ending_at(perp, e_ms - FUTURE_BARS * BAR_MS)
    if e_bar is None or e_24h is None:
        return None
    try:
        ret = btc_ret_24h(e_bar.close, e_24h.close)
        side = btc_side_from_ret(ret)
    except (Market06RowIneligible, Market06IncompleteExecution):
        return None
    rv_closes: list[float] = []
    for k in range(RV_RETURN_COUNT, -1, -1):
        bar = get_perp_bar_ending_at(perp, e_ms - k * BAR_MS)
        if bar is None:
            return None
        rv_closes.append(bar.close)
    try:
        rv = rv_btc_24h(rv_closes)
    except (Market06RowIneligible, Market06IncompleteExecution):
        return None
    entry_bar = get_perp_bar_opening_at(perp, t_ms)
    if entry_bar is None:
        return None
    future: list[PerpBar] = []
    future_closes: list[float] = []
    for k in range(FUTURE_BARS):
        bar = get_perp_bar_opening_at(perp, t_ms + k * BAR_MS)
        if bar is None:
            return None
        if bar.open_time_ms >= PROTECTED_START_MS:
            raise ProtectedYearRefused(f"PROTECTED_FUTURE_BAR:{bar.open_time_ms}")
        future.append(bar)
        future_closes.append(bar.close)
    try:
        severity = arithmetic_mae(side, entry_bar.open, future)
    except (Market06RowIneligible, Market06IncompleteExecution):
        return None
    z: float | None = None
    if require_z:
        table = d_ending
        if table is None:
            if spot is None:
                return None
            table = precompute_d_ending(perp, spot)
        d_e = table.get(e_ms)
        if d_e is None:
            return None
        ref: list[float] = []
        missing_ref = False
        for k in range(1, REFERENCE_COUNT + 1):
            value = table.get(e_ms - k * BAR_MS)
            if value is None:
                missing_ref = True
                break
            ref.append(value)
        if missing_ref:
            return None
        try:
            z = robust_dislocation_z(d_e, ref)[3]
        except (Market06RowIneligible, Market06IncompleteExecution):
            return None
    return DiscoveryRow(
        t_ms=t_ms,
        year=moment.year,
        rv=float(rv),
        ret=float(ret),
        side=float(side),
        severity=float(severity),
        entry_open=float(entry_bar.open),
        future_closes=tuple(future_closes),
        z=None if z is None else float(z),
    )


def build_rows(
    perp: Mapping[int, PerpBar],
    start: datetime,
    end_exclusive: datetime,
    *,
    spot: Mapping[int, float] | None = None,
    require_z: bool = False,
) -> list[DiscoveryRow]:
    d_ending = None
    if require_z:
        if spot is None:
            return []
        d_ending = precompute_d_ending(perp, spot)
    rows: list[DiscoveryRow] = []
    for moment in iter_discovery_decision_times(start, end_exclusive):
        row = construct_discovery_row(
            ms_from_utc(moment),
            perp,
            spot=spot,
            require_z=require_z,
            d_ending=d_ending,
        )
        if row is not None:
            rows.append(row)
    return rows


def rv_abstention_mask(rows: Sequence[DiscoveryRow]) -> np.ndarray:
    rvs = np.asarray([row.rv for row in rows], dtype=np.float64)
    mask = np.zeros(len(rows), dtype=bool)
    for i in range(len(rows)):
        if i < RV_TRAILING_WINDOW:
            continue
        trailing = rvs[i - RV_TRAILING_WINDOW : i]
        threshold = float(np.percentile(trailing, RV_PCTL))
        mask[i] = bool(rvs[i] > threshold)
    return mask


def dislocation_abstention_mask(rows: Sequence[DiscoveryRow]) -> np.ndarray:
    mask = np.zeros(len(rows), dtype=bool)
    for i, row in enumerate(rows):
        if row.z is None:
            continue
        mask[i] = bool(row.z > DISLOCATION_Z_THRESHOLD)
    return mask


def rate_matched_random_abstention(
    years: Sequence[int],
    abstain: np.ndarray,
    *,
    seed: int,
    n_replicates: int = N_REPLICATES,
) -> list[np.ndarray]:
    years_arr = np.asarray(list(years), dtype=np.int64)
    abstain_arr = np.asarray(abstain, dtype=bool)
    if years_arr.shape != abstain_arr.shape:
        raise ValueError("YEAR_ABSTAIN_SHAPE")
    rng = np.random.default_rng(int(seed))
    unique_years = sorted(set(int(y) for y in years_arr.tolist()))
    year_indices = {year: np.flatnonzero(years_arr == year) for year in unique_years}
    year_counts = {year: int(abstain_arr[idx].sum()) for year, idx in year_indices.items()}
    replicates: list[np.ndarray] = []
    n = int(abstain_arr.size)
    for _ in range(int(n_replicates)):
        drawn = np.zeros(n, dtype=bool)
        for year, idx in year_indices.items():
            count = year_counts[year]
            if count == 0:
                continue
            if count > int(idx.size):
                raise ValueError(f"ABSTAIN_COUNT_EXCEEDS_YEAR:{year}")
            chosen = rng.choice(idx, size=count, replace=False)
            drawn[chosen] = True
        if int(drawn.sum()) != int(abstain_arr.sum()):
            raise ValueError("RATE_MATCH_COUNT_MISMATCH")
        replicates.append(drawn)
    return replicates


def evaluate_abstention_delta(
    severity: Sequence[float],
    years: Sequence[int],
    abstain: np.ndarray,
    *,
    seed: int,
    n_replicates: int = N_REPLICATES,
) -> dict[str, Any]:
    sev = np.asarray(list(severity), dtype=np.float64)
    years_arr = np.asarray(list(years), dtype=np.int64)
    mask = np.asarray(abstain, dtype=bool)
    eligible_rule = mask.copy()
    # Trailing-window warmup rows that cannot fire are already False.
    if not mask.any():
        uncond = float(np.mean(sev)) if sev.size else None
        return {
            "ABSTAIN_COUNT": 0,
            "ABSTAIN_RATE": 0.0,
            "MU_RULE": None,
            "MU_CONTROL_MEAN": None,
            "DELTA": None,
            "UNCONDITIONAL_MEAN": uncond,
            "STATISTICAL_THRESHOLD_MET": False,
            "PRACTICAL_MAGNITUDE_MET": False,
            "TEMPORAL_CONSISTENCY_MET": False,
            "YEAR_DELTAS": {},
            "CONTROL_P95": None,
            "N_REPLICATES": int(n_replicates),
            "YEAR_ABSTAIN_COUNTS": {},
        }
    mu_rule = float(np.mean(sev[mask]))
    replicates = rate_matched_random_abstention(
        years_arr, mask, seed=seed, n_replicates=n_replicates
    )
    mu_ctrl = np.asarray([float(np.mean(sev[rep])) for rep in replicates], dtype=np.float64)
    mu_control_mean = float(np.mean(mu_ctrl))
    delta = float(mu_rule - mu_control_mean)
    control_p95 = float(np.percentile(mu_ctrl, 95))
    uncond = float(np.mean(sev))
    statistical = bool(mu_rule > control_p95)
    practical = bool(uncond != 0.0 and delta >= 0.20 * uncond)
    year_deltas: dict[str, float | None] = {}
    positive_years = 0
    year_abstain_counts: dict[str, int] = {}
    present_years = sorted(set(int(y) for y in years_arr.tolist()))
    for year in present_years:
        year_mask = years_arr == year
        year_abstain_counts[str(year)] = int(mask[year_mask].sum())
        if not np.any(mask & year_mask):
            year_deltas[str(year)] = None
            continue
        mu_y = float(np.mean(sev[mask & year_mask]))
        ctrl_y = []
        for rep in replicates:
            sel = rep & year_mask
            if not np.any(sel):
                continue
            ctrl_y.append(float(np.mean(sev[sel])))
        if not ctrl_y:
            year_deltas[str(year)] = None
            continue
        d_y = float(mu_y - float(np.mean(ctrl_y)))
        year_deltas[str(year)] = d_y
        if d_y > 0.0:
            positive_years += 1
    temporal = bool(positive_years >= 3)
    return {
        "ABSTAIN_COUNT": int(mask.sum()),
        "ABSTAIN_RATE": float(mask.mean()),
        "MU_RULE": mu_rule,
        "MU_CONTROL_MEAN": mu_control_mean,
        "DELTA": delta,
        "UNCONDITIONAL_MEAN": uncond,
        "STATISTICAL_THRESHOLD_MET": statistical,
        "PRACTICAL_MAGNITUDE_MET": practical,
        "TEMPORAL_CONSISTENCY_MET": temporal,
        "YEAR_DELTAS": year_deltas,
        "CONTROL_P95": control_p95,
        "N_REPLICATES": int(n_replicates),
        "YEAR_ABSTAIN_COUNTS": year_abstain_counts,
        "POSITIVE_YEAR_COUNT": int(positive_years),
        "PRESENT_YEAR_COUNT": int(len(present_years)),
        "RULE_ELIGIBLE_N": int(eligible_rule.size),
    }


def close_path_functionals(
    entry_open: float, closes: Sequence[float]
) -> dict[str, float]:
    """Unsigned close-path morphology. Closes only; never high/low."""

    if len(closes) != FUTURE_BARS:
        raise ValueError(f"FUTURE_CLOSE_COUNT:{len(closes)}")
    if not math.isfinite(entry_open) or entry_open <= 0.0:
        raise ValueError("NONPOSITIVE_ENTRY_OPEN")
    max_up = 0.0
    max_down = 0.0
    for close in closes:
        up = (float(close) - entry_open) / entry_open
        down = (entry_open - float(close)) / entry_open
        if up > max_up:
            max_up = up
        if down > max_down:
            max_down = down
    max_up = max(0.0, max_up)
    max_down = max(0.0, max_down)
    target = max(max_up, max_down)
    time_to = 0
    for k, close in enumerate(closes):
        up = max(0.0, (float(close) - entry_open) / entry_open)
        down = max(0.0, (entry_open - float(close)) / entry_open)
        if max(up, down) == target:
            time_to = k
            break
    return {
        "MAX_UPSIDE_CLOSE_24H": float(max_up),
        "MAX_DOWNSIDE_CLOSE_24H": float(max_down),
        "TIME_TO_MAX_ABS_CLOSE_EXCURSION": float(time_to),
    }


D3_FUNCTIONALS = (
    "MAX_UPSIDE_CLOSE_24H",
    "MAX_DOWNSIDE_CLOSE_24H",
    "TIME_TO_MAX_ABS_CLOSE_EXCURSION",
)


def path_log_returns(entry_open: float, closes: Sequence[float]) -> np.ndarray:
    prev = float(entry_open)
    out = np.empty(len(closes), dtype=np.float64)
    for i, close in enumerate(closes):
        current = float(close)
        out[i] = math.log(current / prev)
        prev = current
    return out


def compound_close_path(entry_open: float, log_returns: Sequence[float]) -> list[float]:
    price = float(entry_open)
    closes: list[float] = []
    for ret in log_returns:
        price = price * math.exp(float(ret))
        closes.append(price)
    return closes


def slot_pools_from_rows(
    rows: Sequence[DiscoveryRow], *, block_length: int
) -> list[np.ndarray]:
    if FUTURE_BARS % block_length != 0:
        raise ValueError(f"BLOCK_LENGTH_NOT_DIVISOR:{block_length}")
    n_slots = FUTURE_BARS // block_length
    buckets: list[list[np.ndarray]] = [[] for _ in range(n_slots)]
    for row in rows:
        rets = path_log_returns(row.entry_open, row.future_closes)
        for slot in range(n_slots):
            start = slot * block_length
            buckets[slot].append(rets[start : start + block_length].copy())
    return [np.stack(items, axis=0) if items else np.zeros((0, block_length)) for items in buckets]


def stratified_block_bootstrap_paths(
    slot_pools: Sequence[np.ndarray],
    *,
    n_paths: int,
    seed: int,
    entry_open: float = 1.0,
) -> list[list[float]]:
    rng = np.random.default_rng(int(seed))
    n_slots = len(slot_pools)
    block_length = int(slot_pools[0].shape[1]) if n_slots else 0
    paths: list[list[float]] = []
    for _ in range(int(n_paths)):
        pieces: list[np.ndarray] = []
        for slot in range(n_slots):
            pool = slot_pools[slot]
            if pool.shape[0] == 0:
                raise ValueError(f"EMPTY_SLOT_POOL:{slot}")
            idx = int(rng.integers(0, pool.shape[0]))
            pieces.append(pool[idx])
        log_rets = np.concatenate(pieces, axis=0)
        if log_rets.size != FUTURE_BARS:
            raise ValueError(f"SURROGATE_LENGTH:{log_rets.size}")
        paths.append(compound_close_path(entry_open, log_rets))
        if block_length and any(p.shape[1] != block_length for p in slot_pools):
            raise ValueError("SLOT_BLOCK_MISMATCH")
    return paths


def rolling_pearson(x: np.ndarray, y: np.ndarray, window: int = D4_ROLLING_WINDOW) -> np.ndarray:
    if x.shape != y.shape:
        raise ValueError("PAIRED_SHAPE")
    n = int(x.size)
    out = np.full(n, np.nan, dtype=np.float64)
    for i in range(window - 1, n):
        xs = x[i - window + 1 : i + 1]
        ys = y[i - window + 1 : i + 1]
        if np.std(xs) == 0.0 or np.std(ys) == 0.0:
            continue
        out[i] = float(np.corrcoef(xs, ys)[0, 1])
    return out


def finite_series(values: np.ndarray) -> np.ndarray:
    return values[np.isfinite(values)]


def observed_correlation_range(series: np.ndarray) -> float:
    finite = finite_series(series)
    if finite.size == 0:
        return float("nan")
    return float(np.max(finite) - np.min(finite))


def practical_excess_range(observed_range: float, null_range_median: float) -> float:
    return float(observed_range) - float(null_range_median)


def circular_block_bootstrap_paired(
    btc: np.ndarray,
    eth: np.ndarray,
    *,
    block_length: int,
    n_replicates: int,
    seed: int,
) -> Iterable[tuple[np.ndarray, np.ndarray]]:
    n = int(btc.size)
    rng = np.random.default_rng(int(seed))
    n_blocks = int(math.ceil(n / block_length))
    for _ in range(int(n_replicates)):
        starts = rng.integers(0, n, size=n_blocks)
        idx = []
        for start in starts:
            for k in range(block_length):
                idx.append(int((int(start) + k) % n))
        idx = idx[:n]
        take = np.asarray(idx, dtype=np.int64)
        yield btc[take], eth[take]


def current_git_commit(root: Path | None = None) -> str:
    import subprocess

    base = root or repo_root()
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=str(base),
            text=True,
        )
        return out.strip()
    except Exception:  # noqa: BLE001
        return "UNKNOWN"


def year_counts(rows: Sequence[DiscoveryRow]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        key = str(row.year)
        counts[key] = counts.get(key, 0) + 1
    return counts
