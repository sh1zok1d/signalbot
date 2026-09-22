"""Discovery Sprint 04 shared constants and fail-closed guards.

Import does not load market data. Real scientific execution is forbidden
unless a later unit authorizes it. EXECUTION_AUTHORIZED stays false here.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Mapping, Sequence

UTC = timezone.utc

UNIT = "DISCOVERY_SPRINT_04_BATCH_FEASIBILITY_AND_OUTCOME_BLIND_IMPLEMENTATION"
SPRINT_JSON_REL = "docs/research/DISCOVERY_SPRINT_04.json"
POLICY_JSON_REL = "docs/research/HETEROGENEOUS_FAMILY_ROTATION_V3.json"
DECISION_JSON_REL = "docs/research/POST_SPRINT03_PROGRAM_DECISION.json"

CORE_BTC_DATASET_ID = "CORE_BTC_BINANCE_V0"
CORE_BTC_SNAPSHOT_ID = "717d37a404f81eefd58c9a796cc11868c48226baf1de8ffecad5e5607f8dd415"
CORE_BTC_ROOT_REL = "artifacts/research_data/CORE_BTC_BINANCE_V0"
CORE_BTC_SNAPSHOT_DOC_REL = "docs/research_data/CORE_BTC_BINANCE_V0/SNAPSHOT_717d37a4.json"

D13_DATASET_ID = "SPRINT04_BINANCE_SPOT_USDT_DAILY_PANEL_V0"
D13_DOCS_REL = "docs/research_data/SPRINT04_BINANCE_SPOT_USDT_DAILY_PANEL_V0"
D13_RAW_REL = "artifacts/research_data/SPRINT04_BINANCE_SPOT_USDT_DAILY_PANEL_V0/raw"

LEGAL_MONTHS_CORE = tuple(
    f"{year:04d}-{month:02d}" for year in range(2020, 2025) for month in range(1, 13)
)
D13_MONTHS = tuple(
    f"{year:04d}-{month:02d}"
    for year in range(2019, 2025)
    for month in range(1, 13)
    if f"{year:04d}-{month:02d}" >= "2019-12"
)

PROTECTED_START = datetime(2025, 1, 1, tzinfo=UTC)
PROTECTED_START_MS = int(PROTECTED_START.timestamp() * 1000)
LEGAL_START = datetime(2020, 1, 1, tzinfo=UTC)
LEGAL_START_MS = int(LEGAL_START.timestamp() * 1000)
LEGAL_END_INCLUSIVE = date(2024, 12, 31)
BAR_1M_MS = 60_000
HOUR_MS = 3_600_000
DAY_MS = 86_400_000
BARS_PER_HOUR = 60
HOURS_PER_DAY = 24
MINUTE_BARS_PER_DAY = 1440

EXECUTION_AUTHORIZED = False

D12_WINDOW_DAYS = 6
D12_MIN_INCLUDED_DAYS = 5
D12_MIN_US_ELIGIBLE = 8
D12_MIN_PSEUDO_SUNDAYS = 100
D12_N_RANDOMIZATIONS = 10_000
D12_MC_ALPHA = 0.05
D12_PRACTICAL_POSITIVE_N = 7
D12_TEMPORAL_YEARS_REQUIRED = 3
D12_RANDOM_SEED = 20260922196
D12_FIELD = "quote_volume"

D13_FORMATION_DAYS = 7
D13_HOLDING_DAYS = 7
D13_LISTING_AGE_DAYS = 35
D13_LIQUIDITY_WINDOW_DAYS = 28
D13_N_CAP = 100
D13_N_MIN = 20
D13_MIN_WEEKS = 200
D13_N_RANDOMIZATIONS = 10_000
D13_MC_ALPHA = 0.05
D13_TEMPORAL_YEARS_REQUIRED = 3
D13_RANDOM_SEED = 20260922197
D13_FIRST_MONDAY_FLOOR = date(2020, 2, 3)
D13_LAST_HOLDING_SUNDAY = date(2024, 12, 29)
D13_QUINTILES = 5
D13_FEE_LEGS = 4
D13_LAST_DECISION_MONDAY = date(2024, 12, 23)
D13_CANONICALIZATION_VERSION = 1
D13_PINNED_TAKER_FEE = 0.001
D13_FRICTION_FLOOR = D13_FEE_LEGS * D13_PINNED_TAKER_FEE
D13_FEE_AUTHORITY_REL = (
    "docs/research_data/SPRINT04_BINANCE_SPOT_USDT_DAILY_PANEL_V0/fee_authority/PIN.json"
)
D13_TEMPORAL_DEPENDENCE_LIMITATION = (
    "Weekly ICs are non-overlapping by construction, but residual serial "
    "dependence may remain. The sign-flip Monte Carlo does not use a block "
    "bootstrap, Newey-West, refractory period, or alternate null. This is a "
    "declared discovery-stage limitation; independent confirmation may use a "
    "stronger dependence design."
)
IMPLEMENTATION_RELPATHS = (
    "scripts/research/discovery_sprint_04/__init__.py",
    "scripts/research/discovery_sprint_04/common.py",
    "scripts/research/discovery_sprint_04/d12.py",
    "scripts/research/discovery_sprint_04/d13.py",
    "scripts/research/discovery_sprint_04/d13_acquire.py",
    "scripts/research/discovery_sprint_04/d13_exclusions.py",
    "scripts/research/discovery_sprint_04/d13_panel.py",
    "scripts/research/discovery_sprint_04/d13_terminal_mark.py",
    "scripts/research/discovery_sprint_04/evaluate.py",
    "scripts/research/discovery_sprint_04/feasibility.py",
    "scripts/research/discovery_sprint_04/restore_d13_panel.py",
)

_PROTECTED_PERIOD_RE = re.compile(r"(?:^|[^0-9])(2025|2026)-\d{2}")


class ProtectedYearRefused(RuntimeError):
    """Opening a 2025/2026 partition or timestamp was refused."""


class SnapshotIdentityError(RuntimeError):
    """Opened files do not match the frozen snapshot identity."""


class MissingLocalData(RuntimeError):
    """Required frozen local snapshot material is absent."""


class Sprint04IntegrityError(RuntimeError):
    """Frozen Sprint 04 contract was violated."""


class RealScientificOutcomeForbidden(RuntimeError):
    """Real-data D12/D13 scientific outcomes are forbidden in this unit."""


class DeferredD13(RuntimeError):
    """D13 cannot proceed scientifically under a frozen deferred status."""


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


def parse_decimal_string(value: Any, *, field: str) -> float:
    if isinstance(value, bytes):
        value = value.decode("utf-8")
    if not isinstance(value, str):
        raise Sprint04IntegrityError(f"NON_STRING_DECIMAL:{field}:{type(value).__name__}")
    if not re.fullmatch(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?", value):
        raise Sprint04IntegrityError(f"LEXICAL_OR_MALFORMED_DECIMAL:{field}:{value!r}")
    out = float(Decimal(value))
    if not math.isfinite(out):
        raise Sprint04IntegrityError(f"NONFINITE_DECIMAL:{field}:{value!r}")
    return out


def implementation_hashes(repo: Path | None = None) -> dict[str, str]:
    base = repo or repo_root()
    out: dict[str, str] = {}
    for rel in IMPLEMENTATION_RELPATHS:
        path = base / rel
        if not path.is_file():
            raise Sprint04IntegrityError(f"MISSING_IMPLEMENTATION_FILE:{rel}")
        out[rel] = sha256_file(path)
    return out


def canonical_json(obj: Any) -> str:
    return json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


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


def load_sprint(repo: Path | None = None) -> dict[str, Any]:
    base = repo or repo_root()
    return json.loads((base / SPRINT_JSON_REL).read_text(encoding="utf-8"))


def us_transition_dates(sprint: Mapping[str, Any] | None = None) -> list[date]:
    blob = sprint or load_sprint()
    days = blob["CARDS"]["D12"]["DATASET_OR_SOURCE_AUTHORITY"]["US_TRANSITION_DAYS"]
    return [date.fromisoformat(d) for year in sorted(days) for d in days[year]]


def eu_transition_dates(sprint: Mapping[str, Any] | None = None) -> list[date]:
    blob = sprint or load_sprint()
    days = blob["CARDS"]["D12"]["DATASET_OR_SOURCE_AUTHORITY"]["EU_TRANSITION_DAYS"]
    return [date.fromisoformat(d) for year in sorted(days) for d in days[year]]


def nth_sunday(year: int, month: int, n: int) -> date:
    day = date(year, month, 1)
    day += timedelta((6 - day.weekday()) % 7)
    return day + timedelta(7 * (n - 1))


def last_sunday(year: int, month: int) -> date:
    if month == 12:
        day = date(year + 1, 1, 1) - timedelta(1)
    else:
        day = date(year, month + 1, 1) - timedelta(1)
    return day - timedelta((day.weekday() - 6) % 7)


def us_in_dst(day: date) -> bool:
    return nth_sunday(day.year, 3, 2) <= day < nth_sunday(day.year, 11, 1)


def eu_in_dst(day: date) -> bool:
    return last_sunday(day.year, 3) <= day < last_sunday(day.year, 10)


def predicted_delta(sunday: date, *, kind: str) -> int:
    """US spring-forward delta=+1; US fall-back delta=-1."""

    if kind == "US":
        if sunday == nth_sunday(sunday.year, 3, 2):
            return +1
        if sunday == nth_sunday(sunday.year, 11, 1):
            return -1
    if kind == "EU":
        if sunday == last_sunday(sunday.year, 3):
            return +1
        if sunday == last_sunday(sunday.year, 10):
            return -1
    raise Sprint04IntegrityError(f"UNKNOWN_TRANSITION:{kind}:{sunday.isoformat()}")


def window_days(sunday: date) -> tuple[list[date], list[date]]:
    """Monday-Saturday before and after transition Sunday S. S excluded."""

    if sunday.weekday() != 6:
        raise Sprint04IntegrityError(f"NOT_SUNDAY:{sunday.isoformat()}")
    before = [sunday - timedelta(days=k) for k in range(6, 0, -1)]
    after = [sunday + timedelta(days=k) for k in range(1, 7)]
    return before, after


def utc_day(ms: int) -> date:
    return datetime.fromtimestamp(ms / 1000.0, tz=UTC).date()


def date_to_ms(day: date) -> int:
    return int(datetime(day.year, day.month, day.day, tzinfo=UTC).timestamp() * 1000)


def mondays_inclusive(first: date, last: date) -> list[date]:
    if first.weekday() != 0 or last.weekday() != 0:
        raise Sprint04IntegrityError("MONDAY_BOUNDS_NOT_MONDAY")
    out: list[date] = []
    cur = first
    while cur <= last:
        out.append(cur)
        cur += timedelta(days=7)
    return out


def finite(value: float, *, name: str) -> float:
    if not math.isfinite(value):
        raise Sprint04IntegrityError(f"NONFINITE:{name}")
    return float(value)


def classify_from_summary(summary: Mapping[str, Any]) -> str:
    if summary.get("IDENTITY_OK") is not True:
        return "INVALID_DISCOVERY"
    if summary.get("SUPPORT_PASS") is not True:
        return "INCONCLUSIVE_DISCOVERY"
    if (
        summary.get("STATISTICAL_GATE") is True
        and summary.get("PRACTICAL_GATE") is True
        and summary.get("TEMPORAL_GATE") is True
    ):
        return "PROMISING_PROTOTYPE"
    return "NO_USEFUL_STRUCTURE"
