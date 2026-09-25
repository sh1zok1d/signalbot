"""Beta V0.2 data-quality / freshness gate and operational health (pure).

`NO ACTIVE EVENTS` is a claim about CURRENT observability and fails closed: it is
returned only when the latest LIVE evaluation is fresh, the Stage-1 ingestion
heartbeat is healthy, the evaluation materialized, every core family is usable
and no coherence barrier went stale. Otherwise DATA STALE / DATA DEGRADED with the
last successful evaluation time. Nothing here reads a clock: `now` is injected.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Iterable, Mapping, Optional, Sequence

from .config import BetaConfig
from .models import (CORE_FAMILIES, OPEN_STATES, S_DEGRADED, S_EVENT_ACTIVE, S_NO_ACTIVE,
                     S_STALE, S_WATCH, TRIGGERED)

BUCKET = timedelta(minutes=5)


def outage_intervals(events: Iterable[Mapping[str, Any]]) -> list:
    """Stage-1 logs `disconnect` (detail.idle_seconds, anchored at the last good
    message) and `restore`. Returns [(start, end|None)] — end None = still open."""
    out, current = [], None
    for e in sorted(events, key=lambda e: e["ts"]):
        if e["event_type"] == "disconnect":
            if current is None:
                idle = float((e.get("detail") or {}).get("idle_seconds") or 0.0)
                current = e["ts"] - timedelta(seconds=max(idle, 0.0))
        elif e["event_type"] == "restore" and current is not None:
            out.append((current, e["ts"]))
            current = None
    if current is not None:
        out.append((current, None))
    return out


def outage_overlaps(events, start: datetime, end: datetime) -> bool:
    return any(s < end and (e is None or e > start) for s, e in outage_intervals(events))


def venue_states(cfg: BetaConfig, rows: Mapping[str, Mapping[str, Any]],
                 declared_available: Mapping[str, bool], bucket_ts: datetime) -> dict:
    """Per-venue liquidation-vote prerequisites for ONE bucket, by value."""
    out = {}
    for ex in cfg.exchanges:
        r = rows.get(ex) or {"live_bars": 0, "bars": 0, "events": []}
        overlap = outage_overlaps(r.get("events", ()), bucket_ts, bucket_ts + BUCKET)
        live = int(r.get("live_bars", 0))
        out[ex] = {"declared_available": bool(declared_available.get(ex, False)),
                   "live_bars": live, "bars": int(r.get("bars", 0)),
                   "outage_overlap": overlap,
                   "heartbeat_healthy": live == 5 and not overlap}
    return out


def ingestion_heartbeat(cfg: BetaConfig, now: datetime,
                        newest_live_kline: Mapping[str, datetime]) -> dict:
    """Stage-1 ingestion heartbeat from PostgreSQL: the newest LIVE 1m bar per
    venue (bar ts = minute start, so +1m is its close)."""
    max_age = cfg["ingestion"]["heartbeat_max_age_s"]
    ages = {}
    for ex in cfg.exchanges:
        ts = newest_live_kline.get(ex)
        ages[ex] = None if ts is None else (now - (ts + timedelta(minutes=1))).total_seconds()
    healthy = [ex for ex, a in ages.items() if a is not None and a <= max_age]
    return {"ages_s": ages, "healthy_venues": healthy,
            "healthy": len(healthy) >= cfg["ingestion"]["min_healthy_venues"]}


def product_status(cfg: BetaConfig, *, now: datetime, latest_live: Optional[Mapping[str, Any]],
                   open_episodes: Sequence[Any], heartbeat: Mapping[str, Any]) -> dict:
    """Fail-closed user-facing status. `latest_live` = newest LIVE tape row
    ({bucket_ts, snapshot}); `open_episodes` = currently open Episode rows."""
    reasons = []
    if latest_live is None:
        return {"status": S_STALE, "reasons": ["NO_EVALUATION_YET"], "last_good_bucket": None,
                "evaluation_age_s": None}
    snap = latest_live["snapshot"]
    bucket = latest_live["bucket_ts"]
    age = (now - (bucket + BUCKET)).total_seconds()
    base = {"last_good_bucket": bucket, "evaluation_age_s": age}
    if age > cfg["max_state_age_s"] or age < -cfg["max_state_age_s"]:
        return {**base, "status": S_STALE, "reasons": ["EVALUATION_TOO_OLD"]}
    if not heartbeat.get("healthy"):
        reasons.append("INGESTION_HEARTBEAT_UNHEALTHY")
    if not snap.get("materialized"):
        reasons.append("MATERIALIZATION_FAILED")
    if snap.get("stale_barrier"):
        reasons.append("STALE_COHERENCE_BARRIER")
    if not snap.get("evaluation_fresh"):
        reasons.append("EVALUATION_NOT_FRESH")
    fams = snap.get("families") or {}
    for f in CORE_FAMILIES:
        if not (fams.get(f) or {}).get("usable"):
            reasons.append(f"FAMILY_UNUSABLE:{f}")
    if reasons:
        return {**base, "status": S_DEGRADED, "reasons": reasons}
    states = {getattr(e, "state", None) for e in open_episodes}
    if TRIGGERED in states:
        return {**base, "status": S_EVENT_ACTIVE, "reasons": []}
    if states & set(OPEN_STATES):
        return {**base, "status": S_WATCH, "reasons": []}
    return {**base, "status": S_NO_ACTIVE, "reasons": []}


def health_alerts(cfg: BetaConfig, *, now: datetime, heartbeat: Mapping[str, Any],
                  detector_watermark: Optional[datetime], latest_live: Optional[Mapping[str, Any]],
                  runtime: Mapping[str, Mapping[str, Any]], delivery_problems: int,
                  switches) -> list:
    """Owner health alerts (keys are stable; no personal data)."""
    h = cfg.section("health")
    alerts = []
    if not heartbeat.get("healthy"):
        alerts.append({"key": "INGESTION_STALE", "detail": {"healthy_venues": heartbeat.get("healthy_venues")}})

    def _stalled(component: str, limit_s: int) -> bool:
        row = runtime.get(component)
        last = row.get("last_success_at") if row else None
        return last is None or (now - last).total_seconds() > limit_s

    if switches.detection:
        if detector_watermark is None or (now - (detector_watermark + BUCKET)).total_seconds() > h["detector_stall_s"]:
            alerts.append({"key": "DETECTOR_NOT_ADVANCING", "detail": {}})
        if latest_live is not None and not latest_live["snapshot"].get("materialized"):
            alerts.append({"key": "MATERIALIZATION_FAILURE",
                           "detail": {"error": latest_live["snapshot"].get("materialization_error")}})
    if switches.outcome_tracking and _stalled("outcomes", h["outcome_stall_s"]):
        alerts.append({"key": "OUTCOME_TRACKER_NOT_ADVANCING", "detail": {}})
    if switches.enabled and _stalled("bot", h["bot_stall_s"]):
        alerts.append({"key": "BOT_RECEIVER_DOWN", "detail": {}})
    if switches.enabled and _stalled("notifier", h["notifier_stall_s"]):
        alerts.append({"key": "NOTIFIER_NOT_RUNNING", "detail": {}})
    if delivery_problems >= h["delivery_problem_threshold"]:
        alerts.append({"key": "DELIVERY_FAILURE_SPIKE", "detail": {"count": delivery_problems}})
    return alerts
