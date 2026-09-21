"""Exact MARKET-06 Binance USD-M and OKX spot parsers.

Network-free. Retained snapshot bytes are parseable only under an
authenticated one-shot execution permit (red-team F-05): the guard is no
longer a permanent refusal, but it is not removed either.

Every failure raised here is a SOURCE INTEGRITY failure and must abort
canonical execution as MARKET_06_INCOMPLETE_EXECUTION (red-team F-03).
Parser failures must never be downgraded by a caller into "this row is
ineligible", because dropping corrupt observations would silently improve
support.

Window membership is deliberately NOT enforced per object: OKX history
pages are fixed-size and legitimately straddle the window boundary.
Trimming to the frozen window, and every global invariant, belongs to
``market_06_canonical_reconstruction`` where cross-object duplicates and
completeness are actually observable.
"""

from __future__ import annotations

import csv
import io
import json
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from scripts.research import market_06_execution_lifecycle as lifecycle
from scripts.research.market_06_cross_venue_dislocation_authority import (
    Market06IncompleteExecution,
    retained_payload_sha256s,
)


BAR_MS = 300_000
WINDOW_START_MS = int(datetime(2022, 1, 1, tzinfo=timezone.utc).timestamp() * 1000)
WINDOW_END_EXCLUSIVE_MS = int(datetime(2025, 1, 1, tzinfo=timezone.utc).timestamp() * 1000)
BINANCE_SYMBOL = "BTCUSDT"
OKX_INST_ID = "BTC-USDT"
OKX_ROW_WIDTH = 9
OKX_CONFIRM = "1"


@dataclass(frozen=True)
class PerpBar:
    open_time_ms: int
    open: float
    high: float
    low: float
    close: float


@dataclass(frozen=True)
class SpotClose:
    open_time_ms: int
    close: float


def _finite_positive(value: Any, *, where: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise Market06IncompleteExecution(f"NON_NUMERIC:{where}") from exc
    if number != number or number in (float("inf"), float("-inf")) or number <= 0.0:
        raise Market06IncompleteExecution(f"NONFINITE_OR_NONPOSITIVE:{where}")
    return number


def _require_5m(ts: int, *, where: str) -> int:
    if ts % BAR_MS != 0:
        raise Market06IncompleteExecution(f"NOT_5M_ALIGNED:{where}:{ts}")
    return ts


def guard_retained_bytes(data: bytes, *, where: str, permit: Any = None) -> None:
    """Retained market-data bytes require an authenticated permit.

    * no permit  -> refuse (canonical execution is not authorized);
    * valid permit -> allow the exact canonical parser to proceed.

    Non-retained (synthetic) bytes are unaffected, so synthetic parser and
    evaluator tests remain possible with no permit at all.
    """

    import hashlib

    digest = hashlib.sha256(data).hexdigest()
    try:
        retained = retained_payload_sha256s()
    except Exception:  # noqa: BLE001 - identity unavailable => fail closed
        retained = frozenset()
    if digest not in retained:
        return
    if permit is None:
        raise lifecycle.Market06ExecutionNotAuthorized(
            f"real retained MARKET-06 bytes require an execution permit:{where}"
        )
    lifecycle.require_permit(permit)


def parse_binance_klines_csv(text: str, *, source: str = "csv") -> list[PerpBar]:
    reader = csv.reader(io.StringIO(text))
    bars: list[PerpBar] = []
    seen: set[int] = set()
    for row in reader:
        if not row:
            continue
        first = row[0].strip().lower()
        if first in {"open_time", "open time"}:
            continue
        if len(row) < 5:
            raise Market06IncompleteExecution(f"BINANCE_SCHEMA:{source}")
        try:
            raw_ts = int(row[0])
        except (TypeError, ValueError) as exc:
            raise Market06IncompleteExecution(f"BINANCE_TIMESTAMP:{source}") from exc
        ts = _require_5m(raw_ts, where=source)
        if ts in seen:
            raise Market06IncompleteExecution(f"BINANCE_DUPLICATE:{source}:{ts}")
        seen.add(ts)
        open_px = _finite_positive(row[1], where=f"{source}.open")
        high_px = _finite_positive(row[2], where=f"{source}.high")
        low_px = _finite_positive(row[3], where=f"{source}.low")
        close_px = _finite_positive(row[4], where=f"{source}.close")
        if high_px < low_px:
            raise Market06IncompleteExecution(f"BINANCE_HIGH_LT_LOW:{source}:{ts}")
        if not (low_px <= open_px <= high_px) or not (low_px <= close_px <= high_px):
            raise Market06IncompleteExecution(f"BINANCE_OHLC_INCONSISTENT:{source}:{ts}")
        bars.append(
            PerpBar(
                open_time_ms=ts,
                open=open_px,
                high=high_px,
                low=low_px,
                close=close_px,
            )
        )
    bars.sort(key=lambda bar: bar.open_time_ms)
    return bars


def parse_binance_zip_bytes(
    data: bytes,
    *,
    zip_name: str,
    permit: Any = None,
) -> list[PerpBar]:
    guard_retained_bytes(data, where=zip_name, permit=permit)
    if BINANCE_SYMBOL not in zip_name or "-5m-" not in zip_name:
        raise Market06IncompleteExecution(f"BINANCE_IDENTITY:{zip_name}")
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            csv_members = [name for name in archive.namelist() if name.lower().endswith(".csv")]
            if len(csv_members) != 1:
                raise Market06IncompleteExecution(f"BINANCE_ZIP_MEMBERS:{zip_name}")
            raw = archive.read(csv_members[0])
    except zipfile.BadZipFile as exc:
        raise Market06IncompleteExecution(f"BINANCE_BAD_ZIP:{zip_name}") from exc
    return parse_binance_klines_csv(raw.decode("utf-8"), source=zip_name)


def parse_okx_history_body(
    data: bytes,
    *,
    source: str,
    permit: Any = None,
) -> list[SpotClose]:
    guard_retained_bytes(data, where=source, permit=permit)
    try:
        payload = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise Market06IncompleteExecution(f"OKX_JSON:{source}") from exc
    if str(payload.get("code")) != "0":
        raise Market06IncompleteExecution(f"OKX_CODE:{source}:{payload.get('code')}")
    rows = payload.get("data") or []
    if not isinstance(rows, list):
        raise Market06IncompleteExecution(f"OKX_DATA:{source}")
    closes: list[SpotClose] = []
    seen: set[int] = set()
    for row in rows:
        if not isinstance(row, list) or len(row) != OKX_ROW_WIDTH:
            raise Market06IncompleteExecution(f"OKX_SCHEMA:{source}")
        try:
            raw_ts = int(row[0])
        except (TypeError, ValueError) as exc:
            raise Market06IncompleteExecution(f"OKX_TIMESTAMP:{source}") from exc
        ts = _require_5m(raw_ts, where=source)
        confirm = str(row[8])
        if confirm != OKX_CONFIRM:
            raise Market06IncompleteExecution(f"OKX_CONFIRM:{source}:{confirm}")
        if ts in seen:
            raise Market06IncompleteExecution(f"OKX_DUPLICATE:{source}:{ts}")
        seen.add(ts)
        close_px = _finite_positive(row[4], where=f"{source}.close")
        closes.append(SpotClose(open_time_ms=ts, close=close_px))
    closes.sort(key=lambda item: item.open_time_ms)
    return closes


def reconstruct_canonical_dataset(*args: Any, **kwargs: Any) -> Any:
    """Canonical reconstruction lives in ``market_06_canonical_reconstruction``.

    Kept as an explicit redirect so no caller can mistake the old refusal
    stub for the real, permit-gated reconstruction path. Caller authority
    overrides are rejected here before anything else, so an unexpected
    keyword can never surface as a bare TypeError.
    """

    lifecycle.reject_caller_authority_override(args, kwargs)

    from scripts.research.market_06_canonical_reconstruction import (
        reconstruct_canonical_dataset as _reconstruct,
    )

    permit = kwargs.pop("permit_object", None)
    if permit is None:
        raise lifecycle.Market06ExecutionNotAuthorized("MARKET_06_PERMIT_REQUIRED")
    return _reconstruct(permit, **kwargs)
