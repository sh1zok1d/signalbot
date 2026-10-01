"""Stage-1 open-interest as-of change for horizon presentation.

The tape's per-venue ``oi_change_pct`` is within one 5m bucket. Horizon OI reads
the last ``open_interest`` row at or before each window boundary instead, and
never compounds those bucket percents. This module is the pure selection; the
read-only query lives in ``storage/beta_v0_store.py``.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Mapping, Optional, Sequence

OI_ASOF_TOLERANCE = timedelta(minutes=2)


def _finite(value) -> Optional[float]:
    if value is None or isinstance(value, bool):
        return None
    try:
        n = float(value)
    except (TypeError, ValueError):
        return None
    if n != n or n in (float("inf"), float("-inf")):
        return None
    return n


def _identity(row: Mapping) -> tuple:
    return (row.get("oi_raw"), row.get("oi_unit"), row.get("contract_value"))


def pick_oi_asof(rows: Sequence[Mapping], boundary: datetime, *,
                 tolerance: timedelta = OI_ASOF_TOLERANCE) -> Optional[dict]:
    """Last observation with ``boundary - tolerance <= ts <= boundary``.

    Identical rows at that timestamp collapse. Conflicting ``oi_raw``,
    ``oi_unit``, or ``contract_value`` at that timestamp is not a value.
    """
    eligible = []
    for row in rows:
        ts = row.get("ts")
        if ts is None or ts > boundary or ts < boundary - tolerance:
            continue
        eligible.append(row)
    if not eligible:
        return None
    latest = max(row["ts"] for row in eligible)
    at = [row for row in eligible if row["ts"] == latest]
    if len({_identity(row) for row in at}) != 1:
        return None
    row = at[0]
    return {"ts": row["ts"], "oi_raw": row.get("oi_raw"), "oi_unit": row.get("oi_unit"),
            "contract_value": row.get("contract_value")}


def _same_contract(a, b) -> bool:
    if a is None and b is None:
        return True
    left, right = _finite(a), _finite(b)
    if left is None or right is None:
        return False
    return left == right


def venue_oi_change_pct(start: Optional[Mapping], end: Optional[Mapping]) -> Optional[float]:
    """``(end - start) / start * 100`` when unit and contract value match.

    A missing side, a unit change, a contract-value change, or a zero start
    is not a percent. The scale matches ``_oi_feature`` (percent points).
    """
    if not start or not end:
        return None
    unit_s, unit_e = start.get("oi_unit"), end.get("oi_unit")
    if not unit_s or not unit_e or unit_s != unit_e:
        return None
    if not _same_contract(start.get("contract_value"), end.get("contract_value")):
        return None
    raw_s, raw_e = _finite(start.get("oi_raw")), _finite(end.get("oi_raw"))
    if raw_s is None or raw_e is None or raw_s == 0:
        return None
    return (raw_e - raw_s) / raw_s * 100.0
