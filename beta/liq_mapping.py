"""Liquidation rows written before the collector fix (docs/BETA_DATA_RELIABILITY_FIX_PLAN_V1.md R1, R2;
package D2), read honestly without rewriting a single raw or tape byte.

- **Bybit** stored every side swapped until the fix (`liquidations.mapping_version` NULL): the
  notional is right, only the label is wrong. Such rows are read with long and short swapped. A
  5m bucket holding rows of both mappings (the restart) has no clean side and is not measured.
- **OKX** never stored a row until the fix, so its stored «0» was never a measurement. Until its
  first fixed row exists, OKX liquidations are not measured: «н/д» on every surface, out of the
  «k из n» denominator, never READY. After it, a quiet OKX bucket is a real 0.

The cutover comes from the raw rows themselves (first fixed row, last old row per venue), so
the reading is a pure function of immutable data: a replay gives the same answer. Tape rows
written under this module carry `LIQ_MAPPING_KEY`; older rows are corrected when read.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Iterable, Mapping, Optional

BUCKET = timedelta(minutes=5)
LIQ_MAPPING_KEY = "liq_mapping_version"      # top-level tape metrics key of corrected rows
LIQ_MAPPING_VERSION = 2                      # = data_ingestion.base_client.LIQUIDATION_MAPPING_VERSION
SIDE_FIELDS = ("long_liquidation_notional", "short_liquidation_notional")

OLD, NEW, MIXED, UNPROVEN = "OLD", "NEW", "MIXED", "UNPROVEN"


def bucket_state(cutover: Mapping[str, Mapping[str, Any]], exchange: str, bucket_ts: datetime) -> str:
    """How `exchange`'s liquidation rows of the 5m bucket starting at `bucket_ts` were written.

    `cutover[ex]` = {"first_new": ts of the first fixed row or None, "last_old": ts of the last
    old row or None}. Venues other than Bybit and OKX were never affected (NEW)."""
    c = cutover.get(exchange) or {}
    first_new, last_old = c.get("first_new"), c.get("last_old")
    end = bucket_ts + BUCKET
    if exchange == "okx":
        return NEW if first_new is not None and first_new < end else UNPROVEN
    if exchange != "bybit":
        return NEW
    # rows of the fixed mapping exist up to the bucket's end, rows of the old one from its start
    has_new = first_new is not None and first_new < end
    has_old = last_old is not None and last_old >= bucket_ts
    if has_new and has_old:
        return MIXED
    return NEW if has_new else OLD


def correct_venue(values: Mapping[str, Optional[float]], state: str) -> dict:
    """{field: value} of one venue and bucket, read under `state`."""
    if state == OLD:
        return {SIDE_FIELDS[0]: values.get(SIDE_FIELDS[1]), SIDE_FIELDS[1]: values.get(SIDE_FIELDS[0])}
    if state in (MIXED, UNPROVEN, "NO_FEED"):
        return {f: None for f in SIDE_FIELDS}
    return {f: values.get(f) for f in SIDE_FIELDS}


def correct_metrics(metrics: Mapping[str, Any], bucket_ts: datetime,
                    cutover: Mapping[str, Mapping[str, Any]], exchanges: Iterable[str]) -> dict:
    """A tape metrics map with every venue's liquidation keys read honestly, marked as corrected.
    A map that already carries the marker is returned unchanged (never corrected twice)."""
    if metrics.get(LIQ_MAPPING_KEY) is not None:
        return dict(metrics)
    out = dict(metrics)
    for ex in exchanges:
        keys = {f: f"x:{ex}:{f}" for f in SIDE_FIELDS}
        if not any(k in metrics for k in keys.values()):
            continue
        fixed = correct_venue({f: metrics.get(k) for f, k in keys.items()}, bucket_state(cutover, ex, bucket_ts))
        for f, k in keys.items():
            out[k] = fixed[f]
    out[LIQ_MAPPING_KEY] = float(LIQ_MAPPING_VERSION)
    return out


def correct_raw_rows(rows: Iterable[Mapping[str, Any]]) -> list:
    """Raw `liquidations` rows (with `mapping_version`) read honestly: an old Bybit row with its side
    swapped; an old OKX row (none was ever stored) dropped."""
    out = []
    for r in rows:
        if r.get("mapping_version") is None and r.get("exchange") == "bybit":
            r = {**r, "side": {"long": "short", "short": "long"}.get(r.get("side"), r.get("side"))}
        elif r.get("mapping_version") is None and r.get("exchange") == "okx":
            continue
        out.append(dict(r))
    return out


# ---- display (data reliability D2) ------------------------------------------------------------
OKX_LIQ_KEYS = tuple(f"x:okx:{f}" for f in SIDE_FIELDS)


def okx_liq_shown(percentiles: Optional[Mapping[str, Any]]) -> bool:
    """OKX liquidation amounts are printed only once both sides' percentiles are MATURE: 30 days of
    real history, the same condition under which OKX may vote. Until then «н/д»."""
    p = percentiles or {}
    return all(((p.get(k) or {}).get("tier") == "mature") for k in OKX_LIQ_KEYS)


def without_okx_liq(metrics: Mapping[str, Any]) -> dict:
    out = dict(metrics)
    for k in OKX_LIQ_KEYS:
        if k in out:
            out[k] = None
    return out


def mark_okx_lower_bound(horizons: Mapping[str, Any]) -> dict:
    """OKX's feed "doesn't represent the total number of liquidations": a shown OKX sum is a lower
    bound («≥», or «$0*» for an incomplete zero), like Binance's."""
    out = dict(horizons)
    for name, block in horizons.items():
        venues = ((block or {}).get("liquidations") or {}).get("venues") if isinstance(block, Mapping) else None
        if not venues or "okx" not in venues:
            continue
        okx = {side: ({**cell, "lower_bound": True} if cell and not cell.get("missing") else cell)
               for side, cell in (venues.get("okx") or {}).items()}
        out[name] = {**block, "liquidations": {**block["liquidations"], "venues": {**venues, "okx": okx}}}
    return out


# ---- liveness of a separate liquidation channel (OKX) -------------------------------------------
# The collector writes at most one heartbeat a minute while OKX's liquidation channel is acknowledged
# and answers its 25 s text ping or pushes (data_ingestion/okx_client.py, manager.HEARTBEAT_EVERY_S).
# A live channel therefore leaves gaps of about 60–85 s. A bucket is measured only when the
# heartbeats cover it from LIVENESS_LEAD_S before its start to its end with no gap over
# LIVENESS_MAX_GAP_S (150 s): one missed write is tolerated, a refused or dead channel is not. The
# window ends at the bucket's end, which the tape run (after close + grace) has already seen.
LIVENESS_EXCHANGES = ("okx",)
LIVENESS_LEAD_S = 90.0
LIVENESS_MAX_GAP_S = 150.0
NO_FEED = "NO_FEED"


def feed_alive(heartbeats: Iterable[datetime], bucket_ts: datetime) -> bool:
    start = bucket_ts - timedelta(seconds=LIVENESS_LEAD_S)
    end = bucket_ts + BUCKET
    points = sorted(t for t in heartbeats if start <= t <= end)
    if not points:
        return False
    edges = [start] + points + [end]
    return all((b - a).total_seconds() <= LIVENESS_MAX_GAP_S for a, b in zip(edges, edges[1:]))


def apply_liveness(metrics: Mapping[str, Any], bucket_ts: datetime,
                   heartbeats: Mapping[str, Iterable[datetime]]) -> dict:
    """OKX's liquidation keys read None for a bucket its channel did not cover (idempotent)."""
    out = dict(metrics)
    for ex in LIVENESS_EXCHANGES:
        if not feed_alive(heartbeats.get(ex) or (), bucket_ts):
            for f in SIDE_FIELDS:
                if f"x:{ex}:{f}" in out:
                    out[f"x:{ex}:{f}"] = None
    return out
