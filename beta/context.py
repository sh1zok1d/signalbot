"""Beta V0.2 temporal context — episodization V0 and the rolling-1h background.

A deterministic, versioned PROJECTION of the 5m state tape. It never replaces the
tape (the underlying truth) and never changes the detector: the fast 5m detector
(`beta.rules` / `beta.detector`) and its episodes, push timing and forward
outcomes stay exactly as they are. This module adds, per closed 5m bucket:

* context episodes with two INDEPENDENT axes
    - confirmation: the highest detector lifecycle level reached (EARLY / ARMED /
      TRIGGERED), computed with the detector's own `lifecycle()` thresholds;
    - phase: ACTIVE / COOLING / ENDED, from an explicit hysteresis rule;
* a running peak (a real single bucket, knowable as of that bucket);
* the rolling-1h background (last 12 closed 5m buckets, from raw values) with
  its own rolling-1h 30d distribution, computed by the frozen percentile core.

Episodization rule (version label pinned to a parameter digest below):
  entry        the detector entry condition (event QUALIFIES with
               streak == lifecycle.entry_streak) while no same-type episode is open;
  ACTIVE       while the event QUALIFIES or its PRIMARY OBSERVABLE stays beyond the
               (laxer) exit percentile;
  COOLING      from the first bucket whose primary observable is not beyond the
               exit percentile (a missing / non-evaluable bucket counts as such);
  reactivation COOLING -> ACTIVE (same episode) only when the event QUALIFIES again;
  end          ENDED after `cooling_buckets_to_end` consecutive such buckets
               (COOLED_DOWN), or when `max_episode_duration_min` from the start
               bucket is reached (MAX_DURATION);
  opposite     an opposite-side entry while this episode is COOLING ends it
               (SUPERSEDED_BY_OPPOSITE); the new episode inherits its cluster_id.
               (No "reversal" claim — only the factual succession is recorded.)
  peak         the bucket with the most extreme primary observable in the event
               direction; ties keep the earliest; updated only on a strict
               improvement, so the state at t never contains a later bucket.

Nothing here reads forward prices or outcomes.
"""
from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Iterable, Mapping, Optional, Sequence

from analytics.percentile_engine.compute import compute_percentile_snapshot
from analytics.percentile_engine.models import (ConfidenceTierThresholds, PercentileRequest,
                                                PercentileSample)

from .config import (EVENT_TYPES, LIQUIDATION_STRESS_LONG, LIQUIDATION_STRESS_SHORT,
                     POSITION_BUILDUP_COMPRESSION, PRICE_OI_CONTRACTION_DOWN,
                     PRICE_OI_CONTRACTION_UP, TAKER_FLOW_EXTREME_BUY, TAKER_FLOW_EXTREME_SELL,
                     BetaConfig, canonical_json)
from .detector import lifecycle, public_episode_id
from .models import ARMED, EARLY, QUALIFIES, STATE_ORDER, TRIGGERED
from .state_tape import BUCKET, iso, metric_key, sha256_json

PHASE_ACTIVE, PHASE_COOLING, PHASE_ENDED = "ACTIVE", "COOLING", "ENDED"
PHASES = (PHASE_ACTIVE, PHASE_COOLING, PHASE_ENDED)
END_COOLED_DOWN = "COOLED_DOWN"
END_MAX_DURATION = "MAX_DURATION"
END_SUPERSEDED = "SUPERSEDED_BY_OPPOSITE"
END_REASONS = (END_COOLED_DOWN, END_MAX_DURATION, END_SUPERSEDED)
CONFIRMATIONS = (EARLY, ARMED, TRIGGERED)

# Version label -> parameter digest. A parameter change without a NEW label fails
# config loading, so a historical episode can never silently change meaning.
KNOWN_EPISODIZATION_DIGESTS = {
    "BETA_EPISODES_V0": "a156788bd69f39f2503e4de8b79e6966c4de70e8d7ec5c8c252a6b98635c022c",
}
KNOWN_CONTEXT_DIGESTS = {
    "BETA_CONTEXT_1H_V0": "760f4aad68b6e4ea5d12029a9161239f2851f6d5fd5504d0a88de7ceab31821f",
}


class ContextVersionError(ValueError):
    """Episodization / context parameters do not match their pinned version label."""


# ---- primary observables (owner decision: the directional leg) ---------------
@dataclass(frozen=True)
class EventSpec:
    event_type: str
    family: str             # cluster family (opposite sides share it)
    direction: int          # +1: larger is more extreme; -1: smaller (more negative) is
    primary: str            # tape metric key, or "liq:<field>" (sum over healthy venues)
    primary_family: Optional[str]   # consensus family that must be usable (None: per-venue)
    opposite: Optional[str]


EVENT_SPECS = {
    PRICE_OI_CONTRACTION_DOWN: EventSpec(PRICE_OI_CONTRACTION_DOWN, "PRICE_OI_CONTRACTION", -1,
                                         "c:price_move_pct_median", "price_structure",
                                         PRICE_OI_CONTRACTION_UP),
    PRICE_OI_CONTRACTION_UP: EventSpec(PRICE_OI_CONTRACTION_UP, "PRICE_OI_CONTRACTION", +1,
                                       "c:price_move_pct_median", "price_structure",
                                       PRICE_OI_CONTRACTION_DOWN),
    POSITION_BUILDUP_COMPRESSION: EventSpec(POSITION_BUILDUP_COMPRESSION, "POSITION_BUILDUP_COMPRESSION",
                                            +1, "c:oi_change_pct_median", "oi", None),
    TAKER_FLOW_EXTREME_BUY: EventSpec(TAKER_FLOW_EXTREME_BUY, "TAKER_FLOW_EXTREME", +1,
                                      "c:taker_delta_notional_usd_sum", "taker_flow",
                                      TAKER_FLOW_EXTREME_SELL),
    TAKER_FLOW_EXTREME_SELL: EventSpec(TAKER_FLOW_EXTREME_SELL, "TAKER_FLOW_EXTREME", -1,
                                       "c:taker_delta_notional_usd_sum", "taker_flow",
                                       TAKER_FLOW_EXTREME_BUY),
    LIQUIDATION_STRESS_LONG: EventSpec(LIQUIDATION_STRESS_LONG, "LIQUIDATION_STRESS", +1,
                                       "liq:long_liquidation_notional", None, LIQUIDATION_STRESS_SHORT),
    LIQUIDATION_STRESS_SHORT: EventSpec(LIQUIDATION_STRESS_SHORT, "LIQUIDATION_STRESS", +1,
                                        "liq:short_liquidation_notional", None, LIQUIDATION_STRESS_LONG),
}


# ---- versions ------------------------------------------------------------------
def _digest(obj) -> str:
    return hashlib.sha256(canonical_json(obj).encode("utf-8")).hexdigest()


def episodization_payload(cfg: BetaConfig) -> dict:
    ep = cfg.section("episodization")
    return {
        "version": ep["version"],
        "cooling_buckets_to_end": ep["cooling_buckets_to_end"],
        "max_episode_duration_min": ep["max_episode_duration_min"],
        "exit_percentile": {k: float(v) for k, v in ep["exit_percentile"].items()},
        "liquidation_exit_min_venues": ep["liquidation_exit_min_venues"],
        "primary_observables": {et: [s.primary, s.direction] for et, s in EVENT_SPECS.items()},
        "opposites": {et: s.opposite for et, s in EVENT_SPECS.items()},
        "entry": "DETECTOR_ENTRY_STREAK",
        "reactivation": "SAME_TYPE_QUALIFIES_WHILE_COOLING",
        "missing_bucket": "COUNTS_AS_BELOW_EXIT",
        "peak": "STRICT_MAX_DIRECTIONAL_PRIMARY_EARLIEST_TIE",
        "confirmation": "DETECTOR_LIFECYCLE_MAX",
    }


def context_payload(cfg: BetaConfig) -> dict:
    c = cfg.section("context")
    return {
        "version": c["version"], "rolling_buckets": c["rolling_buckets"],
        "labels": [float(c["label_elevated"]), float(c["label_high"]), float(c["label_extreme"])],
        "tail_display_max": float(c["tail_display_max"]),
        "metrics": {"range_width_pct_median": "median over venues of (max high - min low) / first open",
                    "price_move_pct_median": "median over venues of (last close - first open) / first open",
                    "volume_notional_usd_sum": "sum of the 5m cross-venue volume sums"},
        "window": "30d", "timeframe": "1h",
    }


def episodization_digest(cfg: BetaConfig) -> str:
    return _digest(episodization_payload(cfg))


def context_digest(cfg: BetaConfig) -> str:
    return _digest(context_payload(cfg))


def verify_versions(cfg: BetaConfig) -> dict:
    """Fail loudly when parameters changed without a new version label."""
    ev, cv = cfg.section("episodization")["version"], cfg.section("context")["version"]
    ed, cd = episodization_digest(cfg), context_digest(cfg)
    if KNOWN_EPISODIZATION_DIGESTS.get(ev) != ed:
        raise ContextVersionError(f"episodization {ev!r} is not pinned to digest {ed}")
    if KNOWN_CONTEXT_DIGESTS.get(cv) != cd:
        raise ContextVersionError(f"context {cv!r} is not pinned to digest {cd}")
    return {"episodization_version": ev, "episodization_digest": ed,
            "episodization_frozen": bool(cfg.section("episodization")["frozen"]),
            "context_version": cv, "context_digest": cd}


# ---- per-bucket readings -----------------------------------------------------------
def _gate_ok(snapshot: Optional[Mapping[str, Any]]) -> bool:
    return bool(snapshot and snapshot.get("materialized") and snapshot.get("evaluation_fresh")
                and not snapshot.get("stale_barrier"))


def _pct_entry(snapshot, key) -> dict:
    p = ((snapshot or {}).get("percentiles") or {}).get(key) or {}
    return {"rank": p.get("rank"), "tier": p.get("tier")}


def _mature_rank(snapshot, key) -> Optional[float]:
    p = _pct_entry(snapshot, key)
    return float(p["rank"]) if p["rank"] is not None and p["tier"] == "mature" else None


def primary_value(cfg: BetaConfig, spec: EventSpec, snapshot) -> Optional[float]:
    metrics = (snapshot or {}).get("metrics") or {}
    if spec.primary.startswith("liq:"):
        field = spec.primary[4:]
        vals = [metrics.get(metric_key(ex, field)) for ex in cfg.exchanges]
        vals = [float(v) for v in vals if v is not None]
        return math.fsum(vals) if vals else None
    v = metrics.get(spec.primary)
    return None if v is None else float(v)


def beyond_exit(cfg: BetaConfig, spec: EventSpec, snapshot) -> bool:
    """Is the primary observable beyond the (laxer) exit percentile in this bucket?"""
    if not _gate_ok(snapshot):
        return False
    ep = cfg.section("episodization")
    thr = float(ep["exit_percentile"][spec.event_type])
    if spec.primary.startswith("liq:"):
        field = spec.primary[4:]
        n = sum(1 for ex in cfg.exchanges
                if (r := _mature_rank(snapshot, metric_key(ex, field))) is not None and r >= thr)
        return n >= ep["liquidation_exit_min_venues"]
    if not ((snapshot.get("families") or {}).get(spec.primary_family) or {}).get("usable"):
        return False
    rank = _mature_rank(snapshot, spec.primary)
    if rank is None:
        return False
    return rank >= thr if spec.direction > 0 else rank <= thr


def confirmation_for(cfg: BetaConfig, event_type: str, streak: int) -> Optional[str]:
    """The detector's own lifecycle level for a qualifying streak (unchanged semantics)."""
    lc = lifecycle(cfg, event_type)
    if streak < lc.entry_streak:
        return None
    if streak >= lc.triggered_at:
        return TRIGGERED
    if lc.armed_at is not None and streak >= lc.armed_at:
        return ARMED
    return lc.entry_state


def _max_conf(a: Optional[str], b: Optional[str]) -> Optional[str]:
    if a is None:
        return b
    if b is None:
        return a
    return a if STATE_ORDER[a] >= STATE_ORDER[b] else b


def _metric(snapshot, key) -> dict:
    return {"value": ((snapshot.get("metrics") or {}).get(key)), **_pct_entry(snapshot, key)}


def _venue_direction(cfg: BetaConfig, snapshot, family: str, field: str) -> Optional[dict]:
    """Per-venue sign counts over the venues that CONTRIBUTED to the consensus family."""
    fam = (snapshot.get("families") or {}).get(family) or {}
    contributing = [ex for ex in cfg.exchanges if ex in (fam.get("contributing") or ())]
    metrics = snapshot.get("metrics") or {}
    vals = {ex: metrics.get(metric_key(ex, field)) for ex in contributing}
    if not contributing or any(v is None for v in vals.values()):
        return None
    return {"up": sorted(ex for ex, v in vals.items() if v > 0),
            "down": sorted(ex for ex, v in vals.items() if v < 0),
            "flat": sorted(ex for ex, v in vals.items() if v == 0),
            "contributing": len(contributing), "expected": fam.get("expected")}


def bucket_view(cfg: BetaConfig, bucket_ts: datetime, snapshot) -> Optional[dict]:
    """Every displayed value of ONE bucket, taken from that bucket's tape snapshot only."""
    if not snapshot or not snapshot.get("materialized"):
        return None
    ref = snapshot.get("reference") or {}
    fams = snapshot.get("families") or {}
    liq = {}
    for side, field in (("long", "long_liquidation_notional"), ("short", "short_liquidation_notional")):
        per = {ex: (snapshot.get("metrics") or {}).get(metric_key(ex, field)) for ex in cfg.exchanges}
        present = {ex: v for ex, v in per.items() if v is not None}
        liq[side] = {"sum": math.fsum(present.values()) if present else None,
                     "venues_observed": sorted(present),
                     "venues_ranked_high": sorted(
                         ex for ex in cfg.exchanges
                         if (r := _mature_rank(snapshot, metric_key(ex, field))) is not None
                         and r >= cfg.rule("LIQUIDATION_STRESS")["venue_percentile_min"])}
    return {
        "bucket_ts": iso(bucket_ts),
        "price_move_pct": _metric(snapshot, "c:price_move_pct_median"),
        "oi_change_pct": _metric(snapshot, "c:oi_change_pct_median"),
        "range_width_pct": _metric(snapshot, "c:range_width_pct_median"),
        "volume_notional_usd": _metric(snapshot, "c:volume_notional_usd_sum"),
        "taker_delta_notional_usd": _metric(snapshot, "c:taker_delta_notional_usd_sum"),
        "liquidations": liq,
        "reference_price": float(ref["price"]) if ref.get("status") == "OK" else None,
        "coverage": {f: {"available": (fams.get(f) or {}).get("available"),
                         "expected": (fams.get(f) or {}).get("expected"),
                         "usable": bool((fams.get(f) or {}).get("usable"))}
                     for f in ("price_structure", "oi", "volume", "taker_flow")},
        "venue_direction": {
            "price": _venue_direction(cfg, snapshot, "price_structure", "price_move_pct"),
            "oi": _venue_direction(cfg, snapshot, "oi", "oi_change_pct"),
            "taker": _venue_direction(cfg, snapshot, "taker_flow", "taker_delta_notional_usd")},
    }


# ---- episodization step -------------------------------------------------------------
def context_episode_id(symbol: str, event_type: str, start_bucket: datetime, ep_digest: str) -> str:
    raw = f"{symbol}|{event_type}|{start_bucket.isoformat()}|{ep_digest}".encode("utf-8")
    return "CX-" + hashlib.sha256(raw).hexdigest()[:10].upper()


def _ts(s: str) -> datetime:
    return datetime.fromisoformat(s)


def empty_state(cfg: BetaConfig, *, pinned: bool = True) -> dict:
    versions = verify_versions(cfg) if pinned else {
        "episodization_version": cfg.section("episodization")["version"] + "+UNPINNED",
        "episodization_digest": episodization_digest(cfg),
        "episodization_frozen": False,
        "context_version": cfg.section("context")["version"], "context_digest": context_digest(cfg)}
    return {**versions, "rules_digest": cfg.rules_digest, "symbol": cfg.symbol,
            "as_of_bucket": None, "episodes": {}, "last_ended": {}, "now": None,
            "context_1h": None, "input": None}


def _evaluation(snapshot, event_type) -> tuple:
    ev = ((snapshot or {}).get("rule_evaluations") or {}).get(event_type) or {}
    return ev.get("status"), int(ev.get("streak") or 0)


def _end(ep: dict, bucket_ts: datetime, reason: str, superseded_by: Optional[str] = None) -> dict:
    return {**ep, "phase": PHASE_ENDED, "ended_bucket": iso(bucket_ts), "end_reason": reason,
            "superseded_by": superseded_by}


def step_context(cfg: BetaConfig, prev: Optional[Mapping[str, Any]], bucket_ts: datetime,
                 row: Optional[Mapping[str, Any]], context_1h: Optional[Mapping[str, Any]] = None,
                 *, pinned: bool = True) -> dict:
    """State after bucket `bucket_ts`, from the state after the previous bucket and
    this bucket's LIVE tape row (None = no row: counts as a below-exit bucket).
    Pure and deterministic; uses nothing later than `bucket_ts`."""
    state = empty_state(cfg, pinned=pinned) if prev is None else {k: v for k, v in prev.items()}
    if prev is not None and state["episodization_digest"] != episodization_digest(cfg):
        raise ContextVersionError("previous state belongs to a different episodization version")
    if state["as_of_bucket"] is not None and _ts(state["as_of_bucket"]) + BUCKET != bucket_ts:
        raise ValueError("step_context must advance exactly one 5m bucket")
    snapshot = (row or {}).get("snapshot")
    ep_cfg = cfg.section("episodization")
    ttl = timedelta(minutes=ep_cfg["max_episode_duration_min"])
    n_end = ep_cfg["cooling_buckets_to_end"]
    ed = state["episodization_digest"]
    episodes = dict(state["episodes"])
    last_ended = dict(state["last_ended"])
    view = bucket_view(cfg, bucket_ts, snapshot)

    def finish(ep):
        last_ended[ep["event_type"]] = ep
        episodes.pop(ep["event_type"], None)

    # 1) continuation of open episodes (TTL first)
    for et in EVENT_TYPES:
        ep = episodes.get(et)
        if ep is None:
            continue
        spec = EVENT_SPECS[et]
        if bucket_ts - _ts(ep["start_bucket"]) >= ttl:
            finish(_end(ep, bucket_ts, END_MAX_DURATION))
            continue
        status, streak = _evaluation(snapshot, et)
        qualifies = _gate_ok(snapshot) and status == QUALIFIES
        ep = dict(ep, last_bucket=iso(bucket_ts))
        if qualifies:
            if ep["phase"] == PHASE_COOLING:
                ep["reactivations"] += 1
            ep.update(phase=PHASE_ACTIVE, below_exit_run=0, last_active_bucket=iso(bucket_ts),
                      confirmation=_max_conf(ep["confirmation"], confirmation_for(cfg, et, streak)))
            if streak == lifecycle(cfg, et).entry_streak:
                ep["detector_episode_ids"] = ep["detector_episode_ids"] + [
                    public_episode_id(cfg.symbol, et, bucket_ts, cfg.rules_digest)]
        elif beyond_exit(cfg, spec, snapshot):
            ep["below_exit_run"] = 0
            if ep["phase"] == PHASE_ACTIVE:
                ep["last_active_bucket"] = iso(bucket_ts)
        else:
            ep.update(phase=PHASE_COOLING, below_exit_run=ep["below_exit_run"] + 1)
        _update_peak(cfg, spec, ep, bucket_ts, snapshot, view)
        if ep["phase"] == PHASE_COOLING and ep["below_exit_run"] >= n_end:
            finish(_end(ep, bucket_ts, END_COOLED_DOWN))
        else:
            episodes[et] = ep

    # 2) entries (detector entry condition, no same-type episode open)
    opened = []
    for et in EVENT_TYPES:
        if et in episodes:
            continue
        status, streak = _evaluation(snapshot, et)
        if not (_gate_ok(snapshot) and status == QUALIFIES and streak == lifecycle(cfg, et).entry_streak):
            continue
        eid = context_episode_id(cfg.symbol, et, bucket_ts, ed)
        ep = {"episode_id": eid, "cluster_id": eid, "event_type": et,
              "family": EVENT_SPECS[et].family, "direction": EVENT_SPECS[et].direction,
              "start_bucket": iso(bucket_ts), "last_bucket": iso(bucket_ts),
              "last_active_bucket": iso(bucket_ts), "phase": PHASE_ACTIVE,
              "confirmation": confirmation_for(cfg, et, streak), "reactivations": 0,
              "below_exit_run": 0, "peak": None,
              "detector_episode_ids": [public_episode_id(cfg.symbol, et, bucket_ts, cfg.rules_digest)],
              "ended_bucket": None, "end_reason": None, "superseded_by": None,
              "supersedes": None, "episodization_version": state["episodization_version"],
              "episodization_digest": ed, "rules_digest": cfg.rules_digest}
        _update_peak(cfg, EVENT_SPECS[et], ep, bucket_ts, snapshot, view)
        episodes[et] = ep
        opened.append(et)

    # 3) opposite-side succession: a COOLING opposite episode ends, the new one joins its cluster
    for et in opened:
        opp = EVENT_SPECS[et].opposite
        old = episodes.get(opp) if opp else None
        if old is not None and old["phase"] == PHASE_COOLING:
            new = episodes[et]
            finish(_end(old, bucket_ts, END_SUPERSEDED, superseded_by=new["episode_id"]))
            episodes[et] = dict(new, cluster_id=old["cluster_id"], supersedes=old["episode_id"])

    state.update(as_of_bucket=iso(bucket_ts), episodes=episodes, last_ended=last_ended, now=view,
                 context_1h=None if context_1h is None else dict(context_1h),
                 input=None if row is None else {"tape_id": row.get("tape_id"),
                                                 "revision": row.get("revision"),
                                                 "snapshot_digest": row.get("snapshot_digest")})
    return state


def _update_peak(cfg, spec: EventSpec, ep: dict, bucket_ts: datetime, snapshot, view) -> None:
    """Running peak: strict improvement in the event direction only (tie -> earliest)."""
    if view is None:
        return
    v = primary_value(cfg, spec, snapshot)
    if v is None:
        return
    cur = ep["peak"]
    if cur is None or spec.direction * v > spec.direction * cur["primary_value"]:
        ep["peak"] = {"bucket_ts": iso(bucket_ts), "primary_value": v, "view": view}


def state_digest(state: Mapping[str, Any]) -> str:
    return sha256_json(state)


# ---- rolling 1h context --------------------------------------------------------------
def rolling_1h_values(cfg: BetaConfig, metrics_by_bucket: Mapping[datetime, Mapping[str, Any]],
                      end_bucket: datetime) -> Optional[dict]:
    """Raw rolling-1h metrics over the last `rolling_buckets` closed buckets ending at
    `end_bucket` (inclusive). Computed from raw per-bucket values (never from 5m
    percentiles); None when any bucket or required value is missing."""
    n = cfg.section("context")["rolling_buckets"]
    buckets = [end_bucket - i * BUCKET for i in range(n - 1, -1, -1)]
    rows = [metrics_by_bucket.get(b) for b in buckets]
    if any(r is None for r in rows):
        return None
    vols = [r.get("c:volume_notional_usd_sum") for r in rows]
    volume = math.fsum(vols) if all(v is not None for v in vols) else None
    ranges, moves, venues = [], [], []
    for ex in cfg.exchanges:
        o = rows[0].get(metric_key(ex, "kline_open"))
        c = rows[-1].get(metric_key(ex, "kline_close"))
        hs = [r.get(metric_key(ex, "kline_high")) for r in rows]
        ls = [r.get(metric_key(ex, "kline_low")) for r in rows]
        if o is None or c is None or o <= 0 or any(v is None for v in hs + ls):
            continue
        ranges.append((max(hs) - min(ls)) / o * 100.0)
        moves.append((c - o) / o * 100.0)
        venues.append(ex)
    enough = len(venues) >= cfg.min_venues
    return {"window_start": iso(buckets[0]), "window_end": iso(end_bucket + BUCKET),
            "range_width_pct_median": _median(ranges) if enough else None,
            "price_move_pct_median": _median(moves) if enough else None,
            "volume_notional_usd_sum": volume, "venues": venues}


def _median(xs: Sequence[float]) -> float:
    s = sorted(xs)
    m = len(s) // 2
    return s[m] if len(s) % 2 else (s[m - 1] + s[m]) / 2.0


CONTEXT_1H_METRICS = ("range_width_pct_median", "price_move_pct_median", "volume_notional_usd_sum")


def context_1h(cfg: BetaConfig, *, bucket_ts: datetime, current_metrics: Mapping[str, Any],
               history: Iterable[tuple], identity: Mapping[str, Any], code_version: str,
               tiers: Mapping[str, Any]) -> Optional[dict]:
    """Rolling-1h raw values at `bucket_ts` + their percentile against the rolling-1h
    values sampled at every 5m step in [bucket_ts - 30d, bucket_ts) (frozen percentile
    core, timeframe '1h'). `history` = [(bucket_ts, metrics)] strictly before
    `bucket_ts`, reaching back 30d + the rolling window."""
    by_bucket = {b: m for b, m in history if b < bucket_ts}
    by_bucket[bucket_ts] = current_metrics
    cur = rolling_1h_values(cfg, by_bucket, bucket_ts)
    if cur is None:
        return None
    start = bucket_ts - timedelta(days=30)
    samples_at = sorted(b for b in by_bucket if start <= b < bucket_ts)
    series = {b: rolling_1h_values(cfg, by_bucket, b) for b in samples_at}
    thresholds = ConfidenceTierThresholds(
        none_below_days=tiers["none_below_days"], low_below_days=tiers["low_below_days"],
        building_below_days=tiers["building_below_days"])
    out = {**cur, "percentiles": {}}
    for m in CONTEXT_1H_METRICS:
        samples = [PercentileSample(
            scope="consensus", exchange="", symbol=cfg.symbol, market_type=cfg.market_type,
            metric=m, timeframe="1h", bucket_ts=b, value=(v or {}).get(m),
            feature_schema_version=identity["feature_schema_version"],
            calculation_version=identity["calculation_version"]) for b, v in series.items()]
        snap = compute_percentile_snapshot(PercentileRequest(
            scope="consensus", exchange="", symbol=cfg.symbol, market_type=cfg.market_type,
            metric=m, timeframe="1h", percentile_window="30d", bucket_ts=bucket_ts,
            value=cur[m], samples=samples, confidence_tier_thresholds=thresholds,
            config_hash=identity["stage2_config_hash"], config_version=identity["stage2_config_version"],
            code_version=code_version, feature_schema_version=identity["feature_schema_version"],
            calculation_version=identity["calculation_version"]))
        out["percentiles"][m] = {"rank": snap.percentile_rank, "tier": snap.confidence_tier,
                                 "sample_size": snap.sample_size}
    return out


# ---- deterministic labels ------------------------------------------------------------
def level_label(cfg: BetaConfig, rank: Optional[float], tier: Optional[str]) -> Optional[str]:
    """Unsigned dimension label from predefined percentile thresholds (never free text)."""
    if rank is None or tier != "mature":
        return None
    c = cfg.section("context")
    if rank >= c["label_extreme"]:
        return "extreme"
    if rank >= c["label_high"]:
        return "high"
    if rank >= c["label_elevated"]:
        return "elevated"
    return "normal"


def tail_label(cfg: BetaConfig, rank: Optional[float], tier: Optional[str]) -> Optional[str]:
    """Signed-distribution unusualness: 'top 3%' / 'bottom <1%' within the display tail,
    else None. Never claims a literal 100th/0th percentile."""
    if rank is None or tier != "mature":
        return None
    share, side = (1.0 - rank, "top") if rank >= 0.5 else (rank, "bottom")
    if share > cfg.section("context")["tail_display_max"]:
        return None
    return f"{side} <1%" if share < 0.01 else f"{side} {math.ceil(share * 100 - 1e-9):d}%"


# ---- replay -----------------------------------------------------------------------------
def replay(cfg: BetaConfig, rows_by_bucket: Mapping[datetime, Optional[Mapping[str, Any]]],
           *, start_bucket: datetime, end_bucket: datetime,
           initial_state: Optional[Mapping[str, Any]] = None,
           context_1h_by_bucket: Optional[Mapping[datetime, Mapping[str, Any]]] = None) -> list:
    """Recompute the projection bucket by bucket from explicit tape rows (the caller
    chooses the revision policy) under the CONFIGURED episodization version. Returns
    the state after every bucket in [start_bucket, end_bucket]."""
    states, state = [], (dict(initial_state) if initial_state is not None else None)
    b = start_bucket
    while b <= end_bucket:
        state = step_context(cfg, state, b, rows_by_bucket.get(b),
                             (context_1h_by_bucket or {}).get(b))
        states.append(state)
        b += BUCKET
    return states


def episode_structure_stats(cfg: BetaConfig, rows_by_bucket, *, start_bucket: datetime,
                            end_bucket: datetime, candidates: Sequence[int]) -> dict:
    """Condition-series STRUCTURE only (episode count, reactivations, length in
    buckets) per candidate `cooling_buckets_to_end` — for choosing N without ever
    looking at post-event prices or outcomes. Candidates run unpinned (exploratory)."""
    from common.versioning import _to_plain
    out = {}
    for n in candidates:
        raw = _to_plain(cfg.raw)
        raw["episodization"]["cooling_buckets_to_end"] = int(n)
        c = BetaConfig.from_mapping(raw)
        ended, reacts, lengths, state = 0, 0, [], None
        b = start_bucket
        while b <= end_bucket:
            before = {et: e["episode_id"] for et, e in ((state or {}).get("last_ended") or {}).items()}
            state = step_context(c, state, b, rows_by_bucket.get(b), pinned=False)
            for et, e in state["last_ended"].items():
                if before.get(et) != e["episode_id"]:
                    ended += 1
                    reacts += e["reactivations"]
                    lengths.append(int((_ts(e["ended_bucket"]) - _ts(e["start_bucket"])) / BUCKET))
            b += BUCKET
        out[int(n)] = {"episodes_ended": ended, "open_at_end": len(state["episodes"]) if state else 0,
                       "reactivations": reacts,
                       "mean_length_buckets": (sum(lengths) / len(lengths)) if lengths else None}
    return out


# ---- /btc view model (pure data; rendering lives in beta.formatter) --------------------
S_COOLING = "COOLING"
_DATA_PROBLEM = ("DATA STALE", "DATA DEGRADED")


def _display_key(e: Mapping[str, Any]) -> tuple:
    return (0 if e["phase"] == PHASE_ACTIVE else 1,
            -STATE_ORDER.get(e["confirmation"], -1),
            -_ts(e["start_bucket"]).timestamp(),
            EVENT_TYPES.index(e["event_type"]))


def btc_view(cfg: BetaConfig, *, product: Mapping[str, Any], state: Optional[Mapping[str, Any]],
             state_digest_value: Optional[str], now: datetime) -> dict:
    """Everything /btc shows, as plain data. The existing fail-closed product status
    (DATA STALE / DATA DEGRADED) always wins the headline; otherwise the headline is
    the selected context episode's phase (ACTIVE -> the detector vocabulary WATCH /
    EVENT ACTIVE by confirmation; COOLING), or NO ACTIVE EVENTS."""
    status = product["status"]
    usable = state is not None and state.get("as_of_bucket") is not None and (
        product.get("last_good_bucket") is None
        or _ts(state["as_of_bucket"]) >= product["last_good_bucket"])
    episodes = sorted((state or {}).get("episodes", {}).values(), key=_display_key) if usable else []
    shown = episodes[0] if episodes else None
    if status in _DATA_PROBLEM:
        headline = status
    elif shown is None:
        headline = "NO ACTIVE EVENTS"
    elif shown["phase"] == PHASE_COOLING:
        headline = S_COOLING
    else:
        headline = "EVENT ACTIVE" if shown["confirmation"] == TRIGGERED else "WATCH"
    ended = sorted(((state or {}).get("last_ended") or {}).values(),
                   key=lambda e: (_ts(e["ended_bucket"]), EVENT_TYPES.index(e["event_type"])))
    return {
        "headline": headline, "product_status": status, "status_reasons": list(product.get("reasons") or []),
        "requested_at": iso(now),
        "as_of_bucket": (state or {}).get("as_of_bucket") if usable else None,
        "data_through": iso(_ts(state["as_of_bucket"]) + BUCKET) if usable else None,
        "episode": shown, "other_episodes": [[e["event_type"], e["phase"]] for e in episodes[1:]],
        "now": (state or {}).get("now") if usable and status != "DATA STALE" else None,
        "context_1h": (state or {}).get("context_1h") if usable and status != "DATA STALE" else None,
        "last_ended": ended[-1] if (usable and ended) else None,
        "episodization_version": (state or {}).get("episodization_version"),
        "episodization_digest": (state or {}).get("episodization_digest"),
        "episodization_frozen": (state or {}).get("episodization_frozen"),
        "context_version": (state or {}).get("context_version"),
        "context_state_digest": state_digest_value if usable else None,
    }


def find_episode(state: Optional[Mapping[str, Any]], episode_id: str) -> Optional[dict]:
    for e in list(((state or {}).get("episodes") or {}).values()) + \
            list(((state or {}).get("last_ended") or {}).values()):
        if e["episode_id"] == episode_id:
            return e
    return None
