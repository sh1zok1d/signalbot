"""Discovery Sprint 03 shared constants and fail-closed guards.

No import-time market-data reads. Real scientific execution is forbidden
unless a later unit flips EXECUTION_AUTHORIZED.
"""

from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np


UTC = timezone.utc

UNIT = "DISCOVERY_SPRINT_03_BATCH_FEASIBILITY_AND_OUTCOME_BLIND_IMPLEMENTATION"
SPRINT_JSON_REL = "docs/research/DISCOVERY_SPRINT_03.json"
POLICY_JSON_REL = "docs/research/HETEROGENEOUS_FAMILY_ROTATION_V2.json"

M06_DATASET_ID = "MARKET_06_OKX_BINANCE_FEASIBILITY_V0"
M06_SNAPSHOT_ID = "e0403e40a9b1e2903f15fb9283ec6caf54788e48153038982e364d4318183e68"
CORE_BTC_DATASET_ID = "CORE_BTC_BINANCE_V0"
CORE_BTC_SNAPSHOT_ID = "717d37a404f81eefd58c9a796cc11868c48226baf1de8ffecad5e5607f8dd415"
CORE_ETH_DATASET_ID = "CORE_ETH_BINANCE_V0"
CORE_ETH_SNAPSHOT_ID = "4b9c113f659e1c1ca71498096dfdc2628a1016346aed40e19020efb64c85ad15"

CORE_BTC_ROOT_REL = "artifacts/research_data/CORE_BTC_BINANCE_V0"
CORE_ETH_ROOT_REL = "artifacts/research_data/CORE_ETH_BINANCE_V0"
CORE_BTC_SNAPSHOT_DOC_REL = "docs/research_data/CORE_BTC_BINANCE_V0/SNAPSHOT_717d37a4.json"
CORE_ETH_SNAPSHOT_DOC_REL = "docs/research_data/CORE_ETH_BINANCE_V0/SNAPSHOT_4b9c113f.json"
ETH_BINDING_REL = "docs/research_data/CORE_ETH_BINANCE_V0/MARKET_05_EXECUTION_BINDING.json"
M06_HASHES_REL = "docs/research_data/MARKET_06_OKX_BINANCE_FEASIBILITY_V0/HASHES.json"
M06_LEDGER_REL = "docs/research_data/MARKET_06_OKX_BINANCE_FEASIBILITY_V0/binance_object_ledger.json"
D11_SOURCE_REL = "docs/research_data/D11_FOMC_OFFICIAL_V0"

LEGAL_MONTHS = tuple(
    f"{year:04d}-{month:02d}" for year in range(2020, 2025) for month in range(1, 13)
)
CONTROL_YEARS = (2020, 2021, 2022, 2023, 2024)
PROTECTED_START = datetime(2025, 1, 1, tzinfo=UTC)
PROTECTED_START_MS = int(PROTECTED_START.timestamp() * 1000)
LEGAL_START_MS = int(datetime(2020, 1, 1, tzinfo=UTC).timestamp() * 1000)
M06_START_MS = int(datetime(2022, 1, 1, tzinfo=UTC).timestamp() * 1000)

BAR_5M_MS = 300_000
BAR_1M_MS = 60_000
HOUR_MS = 3_600_000
BARS_PER_HOUR = 60

PERCENTILE_METHOD = "linear"
EXECUTION_AUTHORIZED = False

D9_TRAILING_WINDOW = 8640
D9_H_BARS = 12
D9_MIN_EVENT_GAP_BARS = 12
D9_PCTL = 90.0
D9_RV_CUTS = (25.0, 50.0, 75.0)
D9_SEED = 20260922193
D9_CONTROL_SAMPLE_SEED = 202609221931
D9_CONTROL_PERM_SEED = 202609221932
D9_N_RANDOMIZATIONS = 10_000
D9_PRIMARY_LOCATION_STATISTIC = "MEDIAN_PERP_RESOLUTION_SHARE"
D9_NULL_SHARE = 0.5
D9_PRACTICAL_ABS_VS_HALF = 0.10
D9_PRACTICAL_ABS_VS_CONTROL = 0.10
D9_TEMPORAL_YEARS_REQUIRED = 3
D9_TEMPORAL_YEAR_ABS_VS_HALF = 0.05
D9_TEMPORAL_MIN_CLOSING_PER_YEAR = 20
D9_MC_ALPHA = 0.05
D9_MIN_NONOVERLAPPING_EVENTS = 200
D9_MIN_CLOSING_EVENTS = 100
D9_MIN_YEARS_WITH_CLOSING_EVENTS = 3
D9_MIN_MATCHED_CLOSING_CONTROLS = 100
D9_MIN_YEARS_WITH_EVENT_AND_CONTROL = 3

D10_WINDOW = 720
D10_PCTL = 90.0
D10_CONTROL_PCTL = 50.0
D10_RV_CUTS = (25.0, 50.0, 75.0)
D10_SEED = 20260922194
D10_CONTROL_SAMPLE_SEED = 202609221941
D10_N_RANDOMIZATIONS = 10_000
D10_TEMPORAL_DEPENDENCE_LIMITATION = (
    "Discovery-stage limitation: D10 events may cluster in calendar time. "
    "This repair uses 1:1 YEAR x SIGN_E_T x ABS_BTC_RETURN_BUCKET matching and "
    "stratified label permutation inside those frozen strata. It does not add "
    "a post-hoc event refractory or a block bootstrap."
)
D10_REGRESSION_SPECIFICATION = "NO_INTERCEPT_OLS"
D10_PRACTICAL_DELTA = 0.0005
D10_TEMPORAL_YEARS_REQUIRED = 3
D10_MC_ALPHA = 0.05
D10_MIN_EVENTS = 200
D10_MIN_YEARS_WITH_EVENTS = 3
D10_MIN_MATCHED_CONTROLS = 200
D10_MIN_YEARS_WITH_EVENT_AND_CONTROL = 3

D11_HORIZON_HOURS = 6
D11_SEED = 20260922195
D11_N_RANDOMIZATIONS = 10_000
D11_PRACTICAL_RELATIVE = 0.20
D11_TEMPORAL_YEARS_REQUIRED = 3
D11_MC_ALPHA = 0.05
D11_MIN_EVENTS = 20
D11_MIN_YEARS = 3
D11_MIN_CONTROLS_PER_EVENT = 8
D11_MIN_TOTAL_CONTROLS = 80

_PROTECTED_PERIOD_RE = re.compile(r"(?:^|[^0-9])(2025|2026)-\d{2}")


class ProtectedYearRefused(RuntimeError):
    """Opening a 2025/2026 partition or timestamp was refused."""


class SnapshotIdentityError(RuntimeError):
    """Opened files do not match the frozen snapshot identity."""


class MissingLocalData(RuntimeError):
    """Required frozen local snapshot material is absent."""


class Sprint03IntegrityError(RuntimeError):
    """Frozen Sprint 03 contract was violated."""


class RealScientificOutcomeForbidden(RuntimeError):
    """Real-data D9/D10/D11 scientific outcomes are forbidden in this unit."""


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


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def path_is_protected_partition(path: Path) -> bool:
    for part in path.parts:
        if _PROTECTED_PERIOD_RE.search(part):
            return True
        if part.startswith("2025-") or part.startswith("2026-"):
            return True
    return False


def assert_openable(path: Path) -> None:
    if path_is_protected_partition(path):
        raise ProtectedYearRefused(f"PROTECTED_PARTITION_REFUSED:{path}")


def refuse_real_scientific_execution() -> None:
    raise RealScientificOutcomeForbidden(
        "EXECUTION_AUTHORIZED=false; this unit is outcome-blind"
    )


def percentile(values: Sequence[float], p: float) -> float:
    arr = np.asarray(values, dtype=np.float64)
    if arr.size == 0:
        raise Sprint03IntegrityError("EMPTY_PERCENTILE")
    if not np.all(np.isfinite(arr)):
        raise Sprint03IntegrityError("NONFINITE_PERCENTILE")
    return float(np.percentile(arr, p, method=PERCENTILE_METHOD))


def median(values: Sequence[float]) -> float:
    arr = np.asarray(values, dtype=np.float64)
    if arr.size == 0:
        raise Sprint03IntegrityError("EMPTY_MEDIAN")
    if not np.all(np.isfinite(arr)):
        raise Sprint03IntegrityError("NONFINITE_MEDIAN")
    return float(np.median(arr))


def classify_discovery(summary: Mapping[str, Any]) -> str:
    """IDENTITY failure precedes support failure."""

    if not bool(summary.get("IDENTITY_OK", True)):
        return "INVALID_DISCOVERY"
    if not bool(summary.get("SUPPORT_PASS")):
        return "INCONCLUSIVE_DISCOVERY"
    if (
        bool(summary.get("STATISTICAL_GATE"))
        and bool(summary.get("PRACTICAL_GATE"))
        and bool(summary.get("TEMPORAL_GATE"))
    ):
        return "PROMISING_PROTOTYPE"
    return "NO_USEFUL_STRUCTURE"


def cell_rng(seed: int, cell: str) -> np.random.Generator:
    digest = hashlib.sha256(f"{int(seed)}\0{cell}".encode("utf-8")).digest()
    seq = np.random.SeedSequence(
        [
            int(seed),
            int.from_bytes(digest[:8], "little"),
            int.from_bytes(digest[8:16], "little"),
        ]
    )
    return np.random.default_rng(seq)


def sample_matched_ids_per_cell(
    event_ids_by_cell: Mapping[str, Sequence[int]],
    control_ids_by_cell: Mapping[str, Sequence[int]],
    *,
    seed: int,
) -> tuple[dict[str, list[int]], bool]:
    """1:1 without-replacement sample per cell. Outcome-blind; IDs only."""

    matched: dict[str, list[int]] = {}
    used: set[int] = set()
    balanced = True
    for cell in sorted(event_ids_by_cell):
        n_event = len(list(event_ids_by_cell[cell]))
        if n_event == 0:
            matched[cell] = []
            continue
        candidates = sorted(
            {
                int(x)
                for x in control_ids_by_cell.get(cell, [])
                if int(x) not in used
            }
        )
        if len(candidates) < n_event:
            balanced = False
            matched[cell] = []
            continue
        rng = cell_rng(seed, cell)
        order = np.arange(len(candidates))
        rng.shuffle(order)
        chosen = [candidates[int(i)] for i in order[:n_event]]
        for cid in chosen:
            if cid in used:
                raise Sprint03IntegrityError(f"CONTROL_REUSED:{cid}")
            used.add(cid)
        matched[cell] = sorted(chosen)
        if len(matched[cell]) != n_event:
            balanced = False
    return matched, balanced


def stratified_label_permutation_p(
    event_by_cell: Mapping[str, Sequence[float]],
    control_by_cell: Mapping[str, Sequence[float]],
    *,
    observed: float,
    statistic,
    seed: int,
    n: int,
    alternative: str,
) -> float:
    """Permute event/control labels inside each stratum. Never across strata."""

    strata: list[tuple[str, np.ndarray, np.ndarray]] = []
    for cell in sorted(set(event_by_cell) | set(control_by_cell)):
        ev = np.asarray(list(event_by_cell.get(cell, [])), dtype=np.float64)
        ct = np.asarray(list(control_by_cell.get(cell, [])), dtype=np.float64)
        if ev.size == 0 and ct.size == 0:
            continue
        if ev.size != ct.size:
            raise Sprint03IntegrityError(f"STRATUM_UNBALANCED:{cell}:{ev.size}:{ct.size}")
        if not np.all(np.isfinite(ev)) or not np.all(np.isfinite(ct)):
            raise Sprint03IntegrityError(f"NONFINITE_STRATUM:{cell}")
        strata.append((cell, ev, ct))
    if not strata:
        raise Sprint03IntegrityError("EMPTY_STRATIFIED_PERMUTATION")
    rng = np.random.default_rng(seed)
    exceed = 0
    for _ in range(n):
        fake_e: list[np.ndarray] = []
        fake_c: list[np.ndarray] = []
        for _cell, ev, ct in strata:
            pooled = np.concatenate([ev, ct])
            rng.shuffle(pooled)
            fake_e.append(pooled[: ev.size])
            fake_c.append(pooled[ev.size :])
        stat = float(statistic(np.concatenate(fake_e), np.concatenate(fake_c)))
        if alternative == "two-sided-abs":
            if abs(stat) >= abs(observed):
                exceed += 1
        elif alternative == "greater":
            if stat >= observed:
                exceed += 1
        else:
            raise Sprint03IntegrityError(f"BAD_ALTERNATIVE:{alternative}")
    return (1.0 + exceed) / (1.0 + n)


def quantile_bucket(value: float, trailing: Sequence[float]) -> int:
    if len(trailing) < 1:
        raise Sprint03IntegrityError("EMPTY_BUCKET_WINDOW")
    p25, p50, p75 = (
        percentile(trailing, D9_RV_CUTS[0]),
        percentile(trailing, D9_RV_CUTS[1]),
        percentile(trailing, D9_RV_CUTS[2]),
    )
    if value <= p25:
        return 0
    if value <= p50:
        return 1
    if value <= p75:
        return 2
    return 3


def legal_monthly_checksum_key(period: str) -> str:
    return f"canonical/1m/monthly/{period}.parquet"


def legal_monthly_parquet_path(root: Path, period: str) -> Path:
    path = root / "canonical" / "1m" / "monthly" / f"{period}.parquet"
    assert_openable(path)
    return path


def btc_legal_parquet_checksums(repo: Path) -> dict[str, str]:
    import json

    path = repo / CORE_BTC_SNAPSHOT_DOC_REL
    identity = json.loads(path.read_text(encoding="utf-8"))
    payload = identity.get("identity_payload") or identity
    bound = payload.get("snapshot_id") or identity.get("snapshot_id")
    if bound != CORE_BTC_SNAPSHOT_ID:
        raise SnapshotIdentityError(f"BTC_SNAPSHOT_MISMATCH:{bound}")
    checksums = payload.get("output_checksums") or {}
    out: dict[str, str] = {}
    for period in LEGAL_MONTHS:
        key = legal_monthly_checksum_key(period)
        digest = checksums.get(key)
        if not digest:
            raise SnapshotIdentityError(f"BTC_MISSING_CHECKSUM:{period}")
        out[period] = str(digest)
    return out


def eth_legal_parquet_checksums(repo: Path) -> dict[str, str]:
    import json

    snap_path = repo / CORE_ETH_SNAPSHOT_DOC_REL
    snap = json.loads(snap_path.read_text(encoding="utf-8"))
    bound = snap.get("snapshot_id") or snap.get("eth_snapshot_id")
    if bound and bound != CORE_ETH_SNAPSHOT_ID:
        raise SnapshotIdentityError(f"ETH_SNAPSHOT_MISMATCH:{bound}")
    if snap.get("dataset_id") != CORE_ETH_DATASET_ID:
        raise SnapshotIdentityError(f"ETH_DATASET_MISMATCH:{snap.get('dataset_id')}")
    binding = json.loads((repo / ETH_BINDING_REL).read_text(encoding="utf-8"))
    if binding.get("eth_snapshot_id") != CORE_ETH_SNAPSHOT_ID:
        raise SnapshotIdentityError(
            f"ETH_BINDING_SNAPSHOT_MISMATCH:{binding.get('eth_snapshot_id')}"
        )
    out: dict[str, str] = {}
    for obj in binding.get("objects") or []:
        period = str(obj.get("source_period") or "")
        if period not in LEGAL_MONTHS:
            continue
        digest = obj.get("canonical_parquet_sha256")
        if not digest:
            raise SnapshotIdentityError(f"ETH_MISSING_PARQUET_CHECKSUM:{period}")
        out[period] = str(digest)
    if len(out) != len(LEGAL_MONTHS):
        missing = [p for p in LEGAL_MONTHS if p not in out]
        raise SnapshotIdentityError(f"ETH_INCOMPLETE_CHECKSUMS:{missing[:8]}")
    return out


def _read_1m_closes(path: Path) -> list[tuple[int, float]]:
    import pyarrow.parquet as pq

    names = set(pq.read_schema(path).names)
    if "open_time_ms" not in names or "close" not in names:
        raise Sprint03IntegrityError(f"PARQUET_SCHEMA_MISSING:{path}:{sorted(names)}")
    table = pq.read_table(path, columns=["open_time_ms", "close"])
    opens = table.column("open_time_ms").to_pylist()
    closes = table.column("close").to_pylist()
    rows: list[tuple[int, float]] = []
    for raw_open, raw_close in zip(opens, closes):
        open_ms = int(raw_open)
        if open_ms >= PROTECTED_START_MS:
            raise ProtectedYearRefused(f"PROTECTED_TIMESTAMP:{path}:{open_ms}")
        if open_ms < LEGAL_START_MS:
            continue
        close_px = float(raw_close)
        rows.append((open_ms, close_px))
    return rows


def load_hourly_closes(
    *,
    dataset_id: str,
    snapshot_id: str,
    root_rel: str,
    checksums: Mapping[str, str],
    log: OpenedFileLog | None = None,
    repo: Path | None = None,
) -> dict[int, float]:
    """Completed UTC hour last-1m closes. Does not open 1h bars.parquet."""

    base = repo or repo_root()
    root = base / root_rel
    if not root.is_dir():
        raise MissingLocalData(f"{dataset_id}:missing_root:{root}")
    opened = log if log is not None else OpenedFileLog()
    by_open: dict[int, float] = {}
    for period in LEGAL_MONTHS:
        path = legal_monthly_parquet_path(root, period)
        if not path.is_file():
            raise MissingLocalData(f"{dataset_id}:missing_month:{period}")
        raw = path.read_bytes()
        expected = checksums.get(period)
        if expected is None:
            raise SnapshotIdentityError(f"{dataset_id}:missing_checksum:{period}")
        if sha256_bytes(raw) != expected:
            raise SnapshotIdentityError(f"{dataset_id}:checksum_mismatch:{period}")
        opened.record(path, repo_root=base)
        for open_ms, close_px in _read_1m_closes(path):
            if open_ms in by_open and by_open[open_ms] != close_px:
                raise Sprint03IntegrityError(f"{dataset_id}:duplicate_conflict:{open_ms}")
            by_open[open_ms] = close_px
    hours: dict[int, float] = {}
    hour_start = LEGAL_START_MS
    while hour_start < PROTECTED_START_MS:
        complete = True
        last_close = None
        for k in range(BARS_PER_HOUR):
            want = hour_start + k * BAR_1M_MS
            close_px = by_open.get(want)
            if close_px is None or close_px <= 0 or not math.isfinite(close_px):
                complete = False
                break
            last_close = close_px
        if complete and last_close is not None:
            hours[hour_start] = float(last_close)
        hour_start += HOUR_MS
    if not hours:
        raise MissingLocalData(f"{dataset_id}:no_completed_hours")
    return hours


def adjacent_hour_returns(closes: Mapping[int, float]) -> dict[int, float]:
    """r_t = ln(C_t / C_{t-1}) only when t-1 and t are adjacent completed hours."""

    out: dict[int, float] = {}
    for hour_ms, close_px in closes.items():
        prev_ms = hour_ms - HOUR_MS
        prev = closes.get(prev_ms)
        if prev is None or prev <= 0 or close_px <= 0:
            continue
        if hour_ms + HOUR_MS > PROTECTED_START_MS:
            continue
        ret = math.log(close_px / prev)
        if math.isfinite(ret):
            out[hour_ms] = ret
    return out


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
