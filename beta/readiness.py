"""Beta V0.2 detector readiness — a deterministic read model for /btc.

Answers one question per event family for the LATEST closed bucket: could the
existing detector actually evaluate it? It never re-decides anything: READY is
exactly "the detector's own rule evaluation for this bucket was evaluable"
(status QUALIFIES or NOT_QUALIFIES in the tape's `rule_evaluations`). For a
non-evaluable family the same gates the rules use (`beta.rules._base_gate`,
`_families_usable`, `_pct`) classify WHY, and the percentile core's own span
(bucket time minus the earliest valid sample, recorded as `window_start` on
the tape) gives factual history progress. No wall-clock deployment age is used.

States:
  READY             the detector evaluated this family in the latest bucket
  HISTORY_BUILDING  data is arriving; a required percentile is not yet mature
                    (or has no valid history sample yet)
  DATA_UNAVAILABLE  a required input / venue quorum / eligible feed is missing
  DEGRADED          the bucket itself failed a base gate (not materialized,
                    late evaluation, coherence barrier)
  DISABLED          the rule family is switched off in config

Presentation only: nothing here feeds detection, pushes or outcomes.
"""
from __future__ import annotations

import math
from datetime import datetime
from typing import Any, Mapping, Optional

from .config import (LIQUIDATION_STRESS_LONG, LIQUIDATION_STRESS_SHORT, POSITION_BUILDUP_COMPRESSION,
                     PRICE_OI_CONTRACTION_DOWN, PRICE_OI_CONTRACTION_UP, TAKER_FLOW_EXTREME_BUY,
                     TAKER_FLOW_EXTREME_SELL, BetaConfig)
from .models import NOT_EVALUABLE
from .rules import _base_gate, _families_usable, _pct
from .state_tape import iso, metric_key

READINESS_VERSION = "BETA_READINESS_V0"
READY, BUILDING, UNAVAILABLE, DEGRADED, DISABLED = (
    "READY", "HISTORY_BUILDING", "DATA_UNAVAILABLE", "DEGRADED", "DISABLED")
STATES = (READY, BUILDING, UNAVAILABLE, DEGRADED, DISABLED)
# worst-first, for summarising a group whose members are not all READY
_SEVERITY = {DEGRADED: 0, UNAVAILABLE: 1, BUILDING: 2, DISABLED: 3, READY: 4}

# Required inputs per threshold rule, mirroring beta.rules.evaluate_bucket (a test
# checks the mirror against the rules on generated snapshots).
REQUIRED = {
    PRICE_OI_CONTRACTION_DOWN: (("price_structure", "oi"),
                                ("c:price_move_pct_median", "c:oi_change_pct_median")),
    PRICE_OI_CONTRACTION_UP: (("price_structure", "oi"),
                              ("c:price_move_pct_median", "c:oi_change_pct_median")),
    POSITION_BUILDUP_COMPRESSION: (("price_structure", "oi", "volume"),
                                   ("c:range_width_pct_median", "c:oi_change_pct_median",
                                    "c:volume_notional_usd_sum")),
    TAKER_FLOW_EXTREME_BUY: (("taker_flow",), ("c:taker_delta_notional_usd_sum",)),
    TAKER_FLOW_EXTREME_SELL: (("taker_flow",), ("c:taker_delta_notional_usd_sum",)),
}
LIQ_FIELD = {LIQUIDATION_STRESS_LONG: "long_liquidation_notional",
             LIQUIDATION_STRESS_SHORT: "short_liquidation_notional"}
GROUPS = (("PRICE_OI", "Price/OI", (PRICE_OI_CONTRACTION_DOWN, PRICE_OI_CONTRACTION_UP,
                                     POSITION_BUILDUP_COMPRESSION)),
          ("TAKER_FLOW", "Taker flow", (TAKER_FLOW_EXTREME_BUY, TAKER_FLOW_EXTREME_SELL)),
          ("LIQUIDATIONS", "Liquidations", (LIQUIDATION_STRESS_LONG, LIQUIDATION_STRESS_SHORT)))
CORE_GROUP = "PRICE_OI"          # the always-on production scope (taker / liquidation are gated)


def _span_days(entry: Mapping[str, Any], bucket_ts: datetime) -> float:
    """The percentile core's own tier span: bucket time minus the earliest valid sample
    (0 with fewer than two samples). Floored to 0.1 day so it never overstates."""
    if not entry or (entry.get("sample_size") or 0) < 2 or not entry.get("window_start"):
        return 0.0
    span = (bucket_ts - datetime.fromisoformat(entry["window_start"])).total_seconds() / 86400.0
    return math.floor(max(0.0, span) * 10) / 10


def _metric_state(snapshot, key: str, bucket_ts: datetime) -> dict:
    entry = (snapshot.get("percentiles") or {}).get(key) or {}
    _rank, why = _pct(snapshot, key)
    if why is None:
        state = READY
    elif why.startswith("PERCENTILE_NOT_MATURE"):
        state = BUILDING
    elif why.startswith("VALUE_UNAVAILABLE") and entry.get("value") is not None:
        state = BUILDING                  # value measured, but no valid history sample yet
    else:
        state = UNAVAILABLE
    return {"state": state, "reason": why, "tier": entry.get("tier"),
            "sample_size": entry.get("sample_size"), "span_days": _span_days(entry, bucket_ts)}


def _threshold_family(cfg, et: str, snapshot, bucket_ts: datetime) -> dict:
    fams, keys = REQUIRED[et]
    gate = _base_gate(snapshot)
    metrics = {k: _metric_state(snapshot, k, bucket_ts) for k in keys}
    if gate:
        return {"status": DEGRADED, "reason": gate, "metrics": metrics}
    fam_why = _families_usable(snapshot, fams)
    if fam_why:
        return {"status": UNAVAILABLE, "reason": fam_why, "metrics": metrics}
    states = {m["state"] for m in metrics.values()}
    if UNAVAILABLE in states:
        why = next(m["reason"] for m in metrics.values() if m["state"] == UNAVAILABLE)
        return {"status": UNAVAILABLE, "reason": why, "metrics": metrics}
    building = {k: m for k, m in metrics.items() if m["state"] == BUILDING}
    if building:
        k = min(building, key=lambda x: (building[x]["span_days"], x))
        return {"status": BUILDING, "reason": building[k]["reason"], "metrics": metrics,
                "progress": {"metric": k, "span_days": building[k]["span_days"]}}
    return {"status": READY, "reason": None, "metrics": metrics}


def _liquidation_family(cfg, et: str, snapshot, bucket_ts: datetime, ev: Mapping[str, Any],
                        maturity_days: float) -> dict:
    r = cfg.rule("LIQUIDATION_STRESS")
    if not r["enabled"]:
        return {"status": DISABLED, "reason": "RULE_DISABLED"}
    gate = _base_gate(snapshot)
    field = LIQ_FIELD[et]
    detail = ev.get("detail") or {}
    ineligible = detail.get("ineligible") or {}
    venues, building_spans = {}, []
    for ex in cfg.exchanges:
        key = metric_key(ex, field)
        m = _metric_state(snapshot, key, bucket_ts)
        why = ineligible.get(ex)
        if ex in (detail.get("eligible") or ()):
            vstate = READY
            building_spans.append(maturity_days)
        elif why in ("FEED_NOT_DECLARED_AVAILABLE", "HEARTBEAT_UNHEALTHY", "OKX_LIQUIDATIONS_EXCLUDED"):
            vstate = UNAVAILABLE
        else:
            vstate = m["state"] if m["state"] != READY else UNAVAILABLE
            if vstate == BUILDING:
                building_spans.append(m["span_days"])
        venues[ex] = {"state": vstate, "reason": why, "tier": m["tier"], "sample_size": m["sample_size"],
                      "span_days": m["span_days"]}
    base = {"venues": venues, "eligible": list(detail.get("eligible") or []),
            "min_eligible_venues": r["min_eligible_venues"]}
    if gate:
        return {**base, "status": DEGRADED, "reason": gate}
    need = r["min_eligible_venues"]
    if len(building_spans) >= need:
        spans = sorted(building_spans, reverse=True)
        return {**base, "status": BUILDING, "reason": ev.get("reason"),
                "progress": {"metric": f"x:*:{field}", "span_days": spans[need - 1]}}
    return {**base, "status": UNAVAILABLE, "reason": ev.get("reason")}


def family_readiness(cfg: BetaConfig, et: str, snapshot: Mapping[str, Any], bucket_ts: datetime,
                     maturity_days: float) -> dict:
    ev = ((snapshot.get("rule_evaluations") or {}).get(et)) or {}
    rule_status, rule_reason = ev.get("status"), ev.get("reason")
    if rule_status is not None and rule_status != NOT_EVALUABLE:
        # the detector evaluated it; keep the per-input diagnostics for the Details view
        diag = (_liquidation_family(cfg, et, snapshot, bucket_ts, ev, maturity_days) if et in LIQ_FIELD
                else _threshold_family(cfg, et, snapshot, bucket_ts))
        diag.pop("progress", None)
        out = {**diag, "status": READY, "reason": None}
    elif rule_reason == "RULE_DISABLED":
        out = {"status": DISABLED, "reason": rule_reason}
    elif et in LIQ_FIELD:
        out = _liquidation_family(cfg, et, snapshot, bucket_ts, ev, maturity_days)
    else:
        out = _threshold_family(cfg, et, snapshot, bucket_ts)
        if out["status"] == READY:                                 # never READY without the detector
            out = {**out, "status": UNAVAILABLE, "reason": rule_reason or "NOT_EVALUATED"}
    return {**out, "rule_status": rule_status, "rule_reason": rule_reason}


def readiness(cfg: BetaConfig, latest_live: Optional[Mapping[str, Any]], *, maturity_days: float) -> Optional[dict]:
    """Readiness of every family for the latest LIVE tape row ({bucket_ts, snapshot})."""
    if latest_live is None or not latest_live.get("snapshot"):
        return None
    snapshot, bucket_ts = latest_live["snapshot"], latest_live["bucket_ts"]
    events = {et: family_readiness(cfg, et, snapshot, bucket_ts, maturity_days)
              for _g, _l, members in GROUPS for et in members}
    groups = []
    for gid, label, members in GROUPS:
        sts = [events[et]["status"] for et in members]
        enabled = [et for et in members if events[et]["status"] != DISABLED] or list(members)
        ready_n = sum(1 for et in enabled if events[et]["status"] == READY)
        if ready_n == len(enabled) and events[enabled[0]]["status"] == READY:
            status = READY
        else:
            status = min((events[et]["status"] for et in enabled if events[et]["status"] != READY),
                         key=lambda s: _SEVERITY[s])
        limiting = [events[et] for et in enabled if events[et]["status"] == status and events[et].get("progress")]
        progress = min((e["progress"] for e in limiting), key=lambda p: (p["span_days"], p["metric"]),
                       default=None) if status == BUILDING else None
        groups.append({"group": gid, "label": label, "status": status, "members": list(members),
                       "ready_members": ready_n, "enabled_members": len(enabled),
                       "partly_ready": 0 < ready_n < len(enabled), "progress": progress,
                       "reason": next((events[et]["reason"] for et in enabled
                                       if events[et]["status"] == status), None) if status != READY else None,
                       "member_status": {et: events[et]["status"] for et in members}})
    return {"readiness_version": READINESS_VERSION, "bucket_ts": iso(bucket_ts),
            "maturity_days": float(maturity_days), "events": events, "groups": groups,
            "core_ready": next(g for g in groups if g["group"] == CORE_GROUP)["status"] == READY}


def headline(product_status: str, ready: Optional[Mapping[str, Any]]) -> str:
    """Existing fail-closed product status first; NO ACTIVE EVENTS only when the
    production scope (Price/OI) is actually evaluable."""
    if product_status in ("DATA STALE", "DATA DEGRADED", "WATCH", "EVENT ACTIVE"):
        return product_status
    if ready is None:
        return "DETECTOR NOT READY"
    if ready["core_ready"]:
        return product_status                                     # NO ACTIVE EVENTS
    core = next(g for g in ready["groups"] if g["group"] == CORE_GROUP)
    return "HISTORY BUILDING" if (core["status"] == BUILDING or
                                  BUILDING in core["member_status"].values()) else "DETECTOR NOT READY"
