"""Beta V0.2 temporal context — strict detector episodes, recent-event memory and the
rolling-1h background for /btc.

A deterministic, versioned PROJECTION of the 5m state tape. It never replaces the
tape (the underlying truth) and never changes the detector, its pushes or its
forward outcomes.

Active episodization STRICT_QUALIFICATION_V1: the episodes ARE the detector
episodes. The projection replays `beta.detector.step_episode` over the LIVE
decision rows, so an episode opens on the existing detector entry and ends on
the first non-QUALIFIES bucket, a gap, a non-evaluable bucket or a rules /
calculation-version change (POSITION_BUILDUP_COMPRESSION keeps its existing
cap). There is NO hysteresis, no COOLING phase and no invented persistence;
live hysteresis stays disabled (`episodization.live_hysteresis_enabled: false`)
and exists only as unfrozen, taker-only calibration tooling in
`beta.context_calibration`, which no runtime path imports.

What the projection adds per closed bucket:
* the open detector episodes (ACTIVE EVENT) and the most recently ended one per
  event type (LAST EVENT memory, shown for `context.last_event_retention_min`);
* one factual anchor bucket per episode, never a composite:
    - TAKER_FLOW_EXTREME_*: the strongest observed qualifying bucket by signed
      taker delta (strict improvement, earliest tie, knowable as of that bucket);
    - conjunction families (price+OI contraction, build-up/compression) and
      liquidation stress: the detector's own TRIGGER bucket (or the OPENING
      bucket while not triggered) — no "strongest" ranking is invented for a
      conjunction or for per-venue voting;
  every metric shown for the anchor comes from that one bucket;
* NOW (the latest bucket) and the rolling-1h background (raw last-12-bucket
  values ranked by the frozen percentile core against rolling-1h history).
Nothing here reads forward prices or outcomes.
"""
from __future__ import annotations

import hashlib
import math
from dataclasses import asdict, fields
from datetime import datetime, timedelta
from typing import Any, Iterable, Mapping, Optional, Sequence

from analytics.percentile_engine.compute import compute_percentile_snapshot
from analytics.percentile_engine.models import (ConfidenceTierThresholds, PercentileRequest,
                                                PercentileSample)

from .config import (EVENT_TYPES, LIQUIDATION_STRESS_LONG, LIQUIDATION_STRESS_SHORT,
                     TAKER_FLOW_EXTREME_BUY, TAKER_FLOW_EXTREME_SELL, BetaConfig, canonical_json)
from .detector import BucketContext, step_episode
from .models import STATE_ORDER, TRIGGERED, Episode
from .state_tape import BUCKET, TEMPORAL_CONTEXT_SCHEMA_VERSION, iso, metric_key, sha256_json

ACTIVE_EPISODIZATION_VERSION = "STRICT_QUALIFICATION_V1"
# Version label -> parameter digest. A change without a NEW label fails loudly, so a
# recorded state can never silently change meaning.
KNOWN_EPISODIZATION_DIGESTS = {
    "STRICT_QUALIFICATION_V1": "0cce5bc5336d156f2f57fb6794c528d8738e4283e7b4e9846a443003834724f3",
}
KNOWN_CONTEXT_DIGESTS = {
    "BETA_CONTEXT_1H_V0": "7f94fde838a33fb094c6683b8834a2f9accbf96f6fb6d3fcc356aab9f49dc701",
    "BETA_CONTEXT_1H_V1": "59e3df506f7a162f87b69d088fff3d59660dca034efeca48f7f3b4a87ded2576",
    "BETA_CONTEXT_1H_V2": "68ec9dbdb87ad4505d3b000dbc695ec7ff73b638edf9b7624d6acf98c8d63f25",
    "BETA_CONTEXT_1H_V3": "54bcfeff5da06a6d96d0303098275bd4ee881ad0611622b8304a0e16ccb0e035",
}
# A new context version may adopt the episode memory (open episodes, last ended per
# type) of its predecessor's latest snapshot. Episodes depend only on the
# episodization version, so a context-only change must not drop them; without this
# the first bucket under a new label restarts empty and /btc loses its open episodes.
CONTEXT_PREDECESSORS = {"BETA_CONTEXT_1H_V2": ("BETA_CONTEXT_1H_V1",),
                        "BETA_CONTEXT_1H_V3": ("BETA_CONTEXT_1H_V2",)}
# C1 (BETA_CONTEXT_1H_V3, docs/BETA_C1_DAY_TYPE_BASELINE_V1.md): the three metrics evaluated by
# WEEKDAY_WEEKEND_BASELINE_UNIT_V2 are ranked only against samples of the same UTC day type.
DAY_TYPE_METRICS = ("range_width_pct_median", "price_move_pct_median", "volume_notional_usd_sum")
DAY_TYPE_TIER = "day_type_building"
DAY_TYPE_REFERENCE = {
    "rule": "SAME_UTC_DAY_TYPE",
    "day_type": "UTC calendar date of the window start; Saturday or Sunday = WEEKEND, else WEEKDAY",
    "window": "samples at every 5m bucket in [t - 30d, t), filtered to the evaluated window's day type",
    "metrics": list(DAY_TYPE_METRICS),
    "min_same_type_dates": 8,
    "maturity": "the C0 tier over the unfiltered samples must be mature, and >= min_same_type_dates "
                "distinct same-type window-start dates must have a present sample",
    "fallback": "NONE: otherwise the tier is day_type_building (not mature); never the pooled rank",
    "other_metrics": "taker delta and OI change keep the pooled 30-day reference",
    "source": "WEEKDAY_WEEKEND_BASELINE_UNIT_V2 candidate C1 (evaluator 86b2c09)",
}

ANCHOR_STRONGEST = "STRONGEST_OBSERVED_BUCKET"
ANCHOR_TRIGGER = "TRIGGER_BUCKET"
ANCHOR_OPENING = "OPENING_BUCKET"
# Display-only anchor policy. Only the taker families have a single-observable
# intensity (signed taker delta); everything else anchors on detector facts.
STRONGEST_BY = {TAKER_FLOW_EXTREME_BUY: ("c:taker_delta_notional_usd_sum", +1),
                TAKER_FLOW_EXTREME_SELL: ("c:taker_delta_notional_usd_sum", -1)}
LIQUIDATION_TYPES = (LIQUIDATION_STRESS_LONG, LIQUIDATION_STRESS_SHORT)


class ContextVersionError(ValueError):
    """Episodization / context parameters do not match their pinned version label."""


# ---- versions ------------------------------------------------------------------
def _digest(obj) -> str:
    return hashlib.sha256(canonical_json(obj).encode("utf-8")).hexdigest()


def episodization_payload(cfg: BetaConfig) -> dict:
    ep = cfg.section("episodization")
    return {"version": ep["version"], "live_hysteresis_enabled": bool(ep["live_hysteresis_enabled"]),
            "boundaries": "DETECTOR_STEP_EPISODE",
            "anchor": {"strongest_observed": {et: list(v) for et, v in STRONGEST_BY.items()},
                       "otherwise": [ANCHOR_TRIGGER, ANCHOR_OPENING], "tie": "EARLIEST"}}


def context_payload(cfg: BetaConfig) -> dict:
    c = cfg.section("context")
    if c["version"] in _LEGACY_CONTEXT_PAYLOADS:
        return _LEGACY_CONTEXT_PAYLOADS[c["version"]](cfg)
    return {**_context_payload_v2(cfg), "reference": dict(DAY_TYPE_REFERENCE)}


def uses_day_type_reference(cfg: BetaConfig) -> bool:
    """True for BETA_CONTEXT_1H_V3 and later (C1); V0-V2 keep the pooled reference."""
    return cfg.section("context")["version"] not in _LEGACY_CONTEXT_PAYLOADS


def _context_payload_v2(cfg: BetaConfig) -> dict:
    """The BETA_CONTEXT_1H_V2 definition (pooled 30-day reference), frozen so its pinned
    digest stays verifiable; V3 extends it with the day-type reference."""
    c = cfg.section("context")
    return {
        "version": c["version"], "rolling_buckets": c["rolling_buckets"],
        "rolling_buckets_4h": c["rolling_buckets_4h"], "horizons": list(CONTEXT_HORIZONS),
        "labels": [float(c["label_elevated"]), float(c["label_high"]), float(c["label_extreme"])],
        "tail_display_max": float(c["tail_display_max"]),
        "last_event_retention_min": c["last_event_retention_min"],
        "metrics": {"range_width_pct_median": "median over venues of (max high - min low) / first open",
                    "price_move_pct_median": "median over venues of (last close - first open) / first open",
                    "volume_notional_usd_sum": "sum of the 5m cross-venue volume sums",
                    "taker_delta_notional_usd_sum": "sum of the 5m consensus taker delta; every bucket required",
                    "oi_change_pct_median": "median over venues of the Stage-1 open_interest as-of change "
                                            "between the window start and end (2 min tolerance, same unit "
                                            "and contract value); fewer than min_venue_coverage venues is "
                                            "not a value"},
        "window": "30d", "timeframes": {"1h": c["rolling_buckets"], "4h": c["rolling_buckets_4h"]},
        "oi_missing": "only the OI value and rank are missing; other metrics are unchanged",
        "requires_state_schema_version": TEMPORAL_CONTEXT_SCHEMA_VERSION,
        "history_state_schema_versions": "CURRENT_ONLY",
        "carries_episode_memory_from": list(CONTEXT_PREDECESSORS.get(c["version"], ())),
    }


def _context_payload_v1(cfg: BetaConfig) -> dict:
    """The BETA_CONTEXT_1H_V0 / V1 definition, kept so their pinned digests stay
    verifiable (a predecessor's snapshots are looked up by that digest)."""
    c = cfg.section("context")
    return {
        "version": c["version"], "rolling_buckets": c["rolling_buckets"],
        "labels": [float(c["label_elevated"]), float(c["label_high"]), float(c["label_extreme"])],
        "tail_display_max": float(c["tail_display_max"]),
        "last_event_retention_min": c["last_event_retention_min"],
        "metrics": {"range_width_pct_median": "median over venues of (max high - min low) / first open",
                    "price_move_pct_median": "median over venues of (last close - first open) / first open",
                    "volume_notional_usd_sum": "sum of the 5m cross-venue volume sums"},
        "window": "30d", "timeframe": "1h",
        "requires_state_schema_version": TEMPORAL_CONTEXT_SCHEMA_VERSION,
        "history_state_schema_versions": "CURRENT_ONLY",
    }


_LEGACY_CONTEXT_PAYLOADS = {"BETA_CONTEXT_1H_V0": _context_payload_v1, "BETA_CONTEXT_1H_V1": _context_payload_v1,
                            "BETA_CONTEXT_1H_V2": _context_payload_v2}


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
            "live_hysteresis_enabled": False, "context_version": cv, "context_digest": cd}


# ---- per-bucket readings -----------------------------------------------------------
def _pct_entry(snapshot, key) -> dict:
    p = ((snapshot or {}).get("percentiles") or {}).get(key) or {}
    return {"rank": p.get("rank"), "tier": p.get("tier")}


def _metric(snapshot, key) -> dict:
    return {"value": ((snapshot.get("metrics") or {}).get(key)), **_pct_entry(snapshot, key)}


def _venue_direction(cfg: BetaConfig, snapshot, family: str, field: str) -> Optional[dict]:
    """Per-venue sign counts over the venues that CONTRIBUTED to the consensus family."""
    fam = (snapshot.get("families") or {}).get(family) or {}
    contributing = [ex for ex in cfg.exchanges if ex in (fam.get("contributing") or ())]
    raw = snapshot.get("venue_raw") or {}
    vals = {ex: (raw.get(ex) or {}).get(field) for ex in contributing}
    if not contributing or any(v is None for v in vals.values()):
        return None
    return {"up": sorted(ex for ex, v in vals.items() if v > 0),
            "down": sorted(ex for ex, v in vals.items() if v < 0),
            "flat": sorted(ex for ex, v in vals.items() if v == 0),
            "contributing": len(contributing), "expected": fam.get("expected")}


def bucket_view(cfg: BetaConfig, bucket_ts: datetime, snapshot) -> Optional[dict]:
    """Every displayed value of ONE bucket, taken from that bucket's tape snapshot only.
    Liquidations stay per venue with the rule's own eligible/voting evidence — they
    are never summed into a cross-venue intensity."""
    if not snapshot or not snapshot.get("materialized"):
        return None
    ref = snapshot.get("reference") or {}
    fams = snapshot.get("families") or {}
    evals = snapshot.get("rule_evaluations") or {}
    liq = {}
    for et, side, field in ((LIQUIDATION_STRESS_LONG, "long", "long_liquidation_notional"),
                            (LIQUIDATION_STRESS_SHORT, "short", "short_liquidation_notional")):
        ev = evals.get(et) or {}
        detail = ev.get("detail") or {}
        liq[side] = {"per_venue": {ex: (snapshot.get("metrics") or {}).get(metric_key(ex, field))
                                   for ex in cfg.exchanges},
                     "rule_status": ev.get("status"), "eligible": list(detail.get("eligible") or []),
                     "voting": list(detail.get("voting") or [])}
    raw = snapshot.get("venue_raw") or {}
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
        # Numeric per-venue OI percents (the direction map above is only up/down/flat).
        # Presentation reads these from the anchor; they are not detector inputs.
        "oi_change_pct_by_venue": {ex: (raw.get(ex) or {}).get("oi_change_pct") for ex in cfg.exchanges},
    }


# ---- detector episode (de)serialization -------------------------------------------
_EPISODE_TS = {"opened_bucket", "opened_at", "armed_at", "triggered_at", "terminal_at",
               "last_bucket", "reference_bucket"}


def _episode_to(ep: Episode) -> dict:
    d = asdict(ep)
    return {k: (iso(v) if k in _EPISODE_TS else (list(v) if isinstance(v, tuple) else v))
            for k, v in d.items()}


def _episode_from(d: Mapping[str, Any]) -> Episode:
    kw = {}
    for f in fields(Episode):
        v = d.get(f.name)
        if f.name in _EPISODE_TS:
            v = None if v is None else datetime.fromisoformat(v)
        elif f.name == "reference_exchanges":
            v = tuple(v or ())
        kw[f.name] = v
    return Episode(**kw)


def _ts(s: str) -> datetime:
    return datetime.fromisoformat(s)


# ---- strict projection step ------------------------------------------------------------
def empty_state(cfg: BetaConfig) -> dict:
    return {**verify_versions(cfg), "rules_digest": cfg.rules_digest,
            "state_schema_version": cfg.state_schema_version, "symbol": cfg.symbol,
            "as_of_bucket": None, "open": {}, "last_ended": {}, "now": None,
            "context_1h": None, "context_4h": None, "input": None}


def predecessor_context_digests(cfg: BetaConfig) -> list:
    """Pinned digests of the context versions this one may carry episode memory from."""
    return [KNOWN_CONTEXT_DIGESTS[v] for v in CONTEXT_PREDECESSORS.get(cfg.section("context")["version"], ())]


def adopt_predecessor_state(cfg: BetaConfig, prev: Mapping[str, Any]) -> dict:
    """A predecessor context version's state under the CURRENT context identity.

    Only the episode memory (open episodes, last ended per type), the as-of bucket and
    the last input are carried; they depend on the episodization version alone, which
    must match. The context readings are cleared and recomputed from the tape on the
    next step, so no value computed under the old definition is relabelled as new."""
    allowed = set(CONTEXT_PREDECESSORS.get(cfg.section("context")["version"], ()))
    if prev.get("context_version") not in allowed:
        raise ContextVersionError(f"context {prev.get('context_version')!r} is not a declared predecessor")
    if prev.get("episodization_digest") != episodization_digest(cfg):
        raise ContextVersionError("predecessor state belongs to a different episodization version")
    if prev.get("rules_digest") != cfg.rules_digest:
        raise ContextVersionError("predecessor state belongs to a different rules digest")
    state = empty_state(cfg)
    state.update(as_of_bucket=prev.get("as_of_bucket"), open=dict(prev.get("open") or {}),
                 last_ended=dict(prev.get("last_ended") or {}), now=prev.get("now"),
                 input=prev.get("input"))
    return state


def _anchor(kind: str, bucket_ts: datetime, view, ev, value=None) -> dict:
    return {"kind": kind, "bucket_ts": iso(bucket_ts), "view": view,
            "evidence": dict((ev or {}).get("detail") or {}), "value": value}


def _record(cfg: BetaConfig, cur: Optional[Mapping[str, Any]], ep: Episode, *, bucket_ts: datetime,
            snapshot, view, qualifying: bool, triggered_now: bool, ed: str) -> dict:
    rec = dict(cur) if cur is not None else {
        "episode_id": ep.public_id, "event_type": ep.event_type, "qualifying_buckets": 0,
        "anchor": None, "episodization_version": ACTIVE_EPISODIZATION_VERSION,
        "episodization_digest": ed}
    rec.update(state=ep.state, opened_bucket=iso(ep.opened_bucket), last_bucket=iso(ep.last_bucket),
               armed_at=iso(ep.armed_at), triggered_at=iso(ep.triggered_at),
               terminal_at=iso(ep.terminal_at), terminal_reason=ep.terminal_reason,
               detector=_episode_to(ep))
    if not qualifying or view is None:
        return rec
    rec["qualifying_buckets"] = rec["qualifying_buckets"] + 1
    ev = ((snapshot or {}).get("rule_evaluations") or {}).get(ep.event_type)
    if ep.event_type in STRONGEST_BY:
        key, direction = STRONGEST_BY[ep.event_type]
        v = (snapshot.get("metrics") or {}).get(key)
        a = rec["anchor"]
        if v is not None and (a is None or direction * float(v) > direction * a["value"]):
            rec["anchor"] = _anchor(ANCHOR_STRONGEST, bucket_ts, view, ev, float(v))
    elif triggered_now:
        rec["anchor"] = _anchor(ANCHOR_TRIGGER, bucket_ts, view, ev)
    elif rec["anchor"] is None:
        rec["anchor"] = _anchor(ANCHOR_OPENING, bucket_ts, view, ev)
    return rec


def step_context(cfg: BetaConfig, prev: Optional[Mapping[str, Any]], bucket_ts: datetime,
                 row: Optional[Mapping[str, Any]], context_1h: Optional[Mapping[str, Any]] = None,
                 context_4h: Optional[Mapping[str, Any]] = None) -> dict:
    """State after bucket `bucket_ts`, from the state after the previous bucket and this
    bucket's LIVE tape row. The episodes are stepped with the detector's own
    `step_episode` on exactly the inputs the detector used, so their boundaries are the
    detector's. A bucket without a LIVE row was never decided by the detector and is
    not stepped (the next decided bucket then sees the gap, exactly like the
    detector). Pure and deterministic; uses nothing later than `bucket_ts`."""
    state = empty_state(cfg) if prev is None else {k: v for k, v in prev.items()}
    if prev is not None and state["episodization_digest"] != episodization_digest(cfg):
        raise ContextVersionError("previous state belongs to a different episodization version")
    if state["as_of_bucket"] is not None and _ts(state["as_of_bucket"]) + BUCKET != bucket_ts:
        raise ValueError("step_context must advance exactly one 5m bucket")
    ed = state["episodization_digest"]
    snapshot = (row or {}).get("snapshot")
    if snapshot is not None and (snapshot.get("state_schema_version") != state["state_schema_version"]
                                 or state["state_schema_version"] != cfg.state_schema_version):
        # never reinterpret a row of another tape schema under this state's identity
        raise ContextVersionError(
            f"tape row schema {snapshot.get('state_schema_version')} != projection schema "
            f"{state['state_schema_version']} (config {cfg.state_schema_version})")
    view = bucket_view(cfg, bucket_ts, snapshot)
    open_, ended = dict(state["open"]), dict(state["last_ended"])
    evals = (snapshot or {}).get("rule_evaluations")
    if evals is not None:
        ctx = BucketContext(bucket_ts=bucket_ts, decision_ts=bucket_ts + BUCKET,
                            snapshot_digest=row["snapshot_digest"],
                            calculation_version=(snapshot.get("identity") or {})["calculation_version"],
                            reference=snapshot["reference"], code_version=snapshot["code_version"])
        for et in EVENT_TYPES:
            cur = open_.get(et)
            st = step_episode(cfg, et, None if cur is None else _episode_from(cur["detector"]),
                              evals[et], ctx)
            if st.terminated is not None:
                ended[et] = _record(cfg, cur, st.terminated, bucket_ts=bucket_ts, snapshot=snapshot,
                                    view=view, qualifying=False, triggered_now=False, ed=ed)
                open_.pop(et, None)
            if st.updated is not None:
                open_[et] = _record(cfg, cur, st.updated, bucket_ts=bucket_ts, snapshot=snapshot, view=view,
                                    qualifying=True, triggered_now=st.triggered == "updated", ed=ed)
            if st.opened is not None:
                open_[et] = _record(cfg, None, st.opened, bucket_ts=bucket_ts, snapshot=snapshot, view=view,
                                    qualifying=True, triggered_now=st.triggered == "opened", ed=ed)
    state.update(as_of_bucket=iso(bucket_ts), open=open_, last_ended=ended, now=view,
                 context_1h=None if context_1h is None else dict(context_1h),
                 context_4h=None if context_4h is None else dict(context_4h),
                 input=None if row is None else {"tape_id": row.get("tape_id"),
                                                 "revision": row.get("revision"),
                                                 "snapshot_digest": row.get("snapshot_digest")})
    return state


def state_digest(state: Mapping[str, Any]) -> str:
    return sha256_json(state)


# ---- rolling 1h context --------------------------------------------------------------
def rolling_1h_values(cfg: BetaConfig, metrics_by_bucket: Mapping[datetime, Mapping[str, Any]],
                      end_bucket: datetime) -> Optional[dict]:
    """Raw rolling-1h metrics over the last `rolling_buckets` closed buckets ending at
    `end_bucket` (inclusive). Computed from raw per-bucket values (never from 5m
    percentiles); None when any bucket or required value is missing."""
    return rolling_window_values(cfg, metrics_by_bucket, end_bucket,
                                 cfg.section("context")["rolling_buckets"])


def rolling_window_values(cfg: BetaConfig, metrics_by_bucket: Mapping[datetime, Mapping[str, Any]],
                          end_bucket: datetime, n: int) -> Optional[dict]:
    """The rolling-1h computation over the last `n` closed buckets (12 = 1h, 48 = 4h).
    None when any bucket is missing. Volume and taker delta need every bucket's value;
    a missing value is not a partial sum."""
    buckets = [end_bucket - i * BUCKET for i in range(n - 1, -1, -1)]
    rows = [metrics_by_bucket.get(b) for b in buckets]
    if any(r is None for r in rows):
        return None
    vols = [r.get("c:volume_notional_usd_sum") for r in rows]
    volume = math.fsum(vols) if all(v is not None for v in vols) else None
    takers = [r.get("c:taker_delta_notional_usd_sum") for r in rows]
    taker = math.fsum(takers) if all(v is not None for v in takers) else None
    ranges, moves, venues, opens, closes = [], [], [], [], []
    for ex in cfg.exchanges:
        o = rows[0].get(metric_key(ex, "kline_open"))
        c = rows[-1].get(metric_key(ex, "kline_close"))
        hs = [r.get(metric_key(ex, "kline_high")) for r in rows]
        ls = [r.get(metric_key(ex, "kline_low")) for r in rows]
        if o is None or c is None or o <= 0 or any(v is None for v in hs + ls):
            continue
        ranges.append((max(hs) - min(ls)) / o * 100.0)
        moves.append((c - o) / o * 100.0)
        opens.append(float(o))
        closes.append(float(c))
        venues.append(ex)
    enough = len(venues) >= cfg.min_venues
    return {"window_start": iso(buckets[0]), "window_end": iso(end_bucket + BUCKET),
            "range_width_pct_median": _median(ranges) if enough else None,
            "price_move_pct_median": _median(moves) if enough else None,
            "volume_notional_usd_sum": volume, "venues": venues,
            "taker_delta_notional_usd_sum": taker,
            "price_move_pct_by_venue": dict(zip(venues, moves)),
            # presentation only (the push and /catchup price line); medians over venues
            "open_median": _median(opens) if enough else None,
            "close_median": _median(closes) if enough else None}


def _median(xs: Sequence[float]) -> float:
    s = sorted(xs)
    m = len(s) // 2
    return s[m] if len(s) % 2 else (s[m - 1] + s[m]) / 2.0


CONTEXT_1H_METRICS = ("range_width_pct_median", "price_move_pct_median", "volume_notional_usd_sum")
# BETA_CONTEXT_1H_V2: the same three plus the signed taker delta and the Stage-1
# as-of OI change, ranked the same way, for both the 1h and the 4h window.
CONTEXT_METRICS = CONTEXT_1H_METRICS + ("taker_delta_notional_usd_sum", "oi_change_pct_median")
CONTEXT_HORIZONS = ("1h", "4h")
OI_UNAVAILABLE = "OI_UNAVAILABLE"


def horizon_buckets(cfg: BetaConfig) -> dict:
    c = cfg.section("context")
    return {"1h": int(c["rolling_buckets"]), "4h": int(c["rolling_buckets_4h"])}


def history_span(cfg: BetaConfig) -> timedelta:
    """How far back the tape history must reach for every horizon's 30d ranks."""
    return timedelta(days=30) + (max(horizon_buckets(cfg).values()) - 1) * BUCKET


def _with_oi(cfg: BetaConfig, values: Optional[dict], oi_index, end_bucket: datetime,
             n: int) -> Optional[dict]:
    if values is None:
        return None
    from .oi_asof import window_oi_change
    end = end_bucket + BUCKET
    oi = window_oi_change(oi_index, cfg.exchanges, end - n * BUCKET, end, min_venues=cfg.min_venues)
    return {**values, **oi}


def context_1h(cfg: BetaConfig, *, bucket_ts: datetime, current_metrics: Mapping[str, Any],
               history: Iterable[tuple], identity: Mapping[str, Any], code_version: str,
               tiers: Mapping[str, Any], oi_index=None, horizon: str = "1h") -> Optional[dict]:
    """Rolling raw values at `bucket_ts` + their percentile against the same rolling
    values sampled at every 5m step in [bucket_ts - 30d, bucket_ts) (frozen percentile
    core). `history` = [(bucket_ts, metrics)] strictly before `bucket_ts`, reaching
    back 30d + the rolling window. `horizon` picks the window ("1h" = 12 buckets,
    "4h" = 48). OI comes from `oi_index` (Stage-1 as-of); without it the OI value and
    rank are missing and everything else is unchanged."""
    n = horizon_buckets(cfg)[horizon]
    by_bucket = {b: m for b, m in history if b < bucket_ts}
    by_bucket[bucket_ts] = current_metrics
    cur = _with_oi(cfg, rolling_window_values(cfg, by_bucket, bucket_ts, n), oi_index, bucket_ts, n)
    if cur is None:
        return None
    start = bucket_ts - timedelta(days=30)
    samples_at = sorted(b for b in by_bucket if start <= b < bucket_ts)
    series = {b: _with_oi(cfg, rolling_window_values(cfg, by_bucket, b, n), oi_index, b, n)
              for b in samples_at}
    thresholds = ConfidenceTierThresholds(
        none_below_days=tiers["none_below_days"], low_below_days=tiers["low_below_days"],
        building_below_days=tiers["building_below_days"])
    out = {**cur, "horizon": horizon, "rolling_buckets": n,
           "oi_status": "OK" if oi_index is not None else OI_UNAVAILABLE, "percentiles": {}}
    day_type = uses_day_type_reference(cfg)
    if day_type:
        from .day_type import MIN_SAME_TYPE_DATES, window_day_type, window_start_date
        own_type = window_day_type(bucket_ts, n)
        out["day_type"] = own_type
        same_type = {b for b in series if window_day_type(b, n) == own_type}

    def _snap(m, items):
        samples = [PercentileSample(
            scope="consensus", exchange="", symbol=cfg.symbol, market_type=cfg.market_type,
            metric=m, timeframe=horizon, bucket_ts=b, value=(v or {}).get(m),
            feature_schema_version=identity["feature_schema_version"],
            calculation_version=identity["calculation_version"]) for b, v in items]
        return compute_percentile_snapshot(PercentileRequest(
            scope="consensus", exchange="", symbol=cfg.symbol, market_type=cfg.market_type,
            metric=m, timeframe=horizon, percentile_window="30d", bucket_ts=bucket_ts,
            value=cur[m], samples=samples, confidence_tier_thresholds=thresholds,
            config_hash=identity["stage2_config_hash"], config_version=identity["stage2_config_version"],
            code_version=code_version, feature_schema_version=identity["feature_schema_version"],
            calculation_version=identity["calculation_version"]))

    for m in CONTEXT_METRICS:
        snap = _snap(m, series.items())
        entry = {"rank": snap.percentile_rank, "tier": snap.confidence_tier, "sample_size": snap.sample_size}
        if day_type and m in DAY_TYPE_METRICS:
            items = [(b, v) for b, v in series.items() if b in same_type]
            present = [b for b, v in items if (v or {}).get(m) is not None]
            dates = len({window_start_date(b, n) for b in present})
            own = _snap(m, items)
            tier = snap.confidence_tier          # C0 maturity over the unfiltered samples
            if tier == "mature" and dates < MIN_SAME_TYPE_DATES:
                tier = DAY_TYPE_TIER             # no fallback to the pooled rank
            entry = {"rank": own.percentile_rank, "tier": tier, "sample_size": own.sample_size,
                     "reference": DAY_TYPE_REFERENCE["rule"], "day_type": own_type, "same_type_dates": dates}
        out["percentiles"][m] = entry
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
           context_1h_by_bucket: Optional[Mapping[datetime, Mapping[str, Any]]] = None,
           context_4h_by_bucket: Optional[Mapping[datetime, Mapping[str, Any]]] = None) -> list:
    """Recompute the projection bucket by bucket from explicit tape rows (the caller
    chooses the revision policy) under the CONFIGURED episodization version."""
    states, state = [], (dict(initial_state) if initial_state is not None else None)
    b = start_bucket
    while b <= end_bucket:
        state = step_context(cfg, state, b, rows_by_bucket.get(b), (context_1h_by_bucket or {}).get(b),
                             (context_4h_by_bucket or {}).get(b))
        states.append(state)
        b += BUCKET
    return states


# ---- /btc view model (pure data; rendering lives in beta.formatter) --------------------
_DATA_PROBLEM = ("DATA STALE", "DATA DEGRADED")


def _display_key(e: Mapping[str, Any]) -> tuple:
    return (-STATE_ORDER.get(e["state"], -1), -_ts(e["opened_bucket"]).timestamp(),
            EVENT_TYPES.index(e["event_type"]))


def btc_view(cfg: BetaConfig, *, product: Mapping[str, Any], state: Optional[Mapping[str, Any]],
             state_digest_value: Optional[str], now: datetime, readiness: Optional[Mapping[str, Any]],
             detector_open_ids: Optional[Iterable[str]] = None,
             horizons: Optional[Mapping[str, Any]] = None) -> dict:
    """Everything /btc shows, as plain data. Headline precedence: DATA STALE, DATA
    DEGRADED, WATCH / EVENT ACTIVE (the existing fail-closed product status, never
    changed here), then — when the product status is NO ACTIVE EVENTS — HISTORY
    BUILDING / DETECTOR NOT READY unless the production scope (Price/OI) is READY
    (`beta.readiness`); only then NO ACTIVE EVENTS. ACTIVE EVENT = an open detector episode;
    LAST EVENT = the most recently ended detector episode, shown only while no episode
    is open and for at most `context.last_event_retention_min` after it ended."""
    usable = state is not None and state.get("as_of_bucket") is not None and (
        product.get("last_good_bucket") is None
        or _ts(state["as_of_bucket"]) >= product["last_good_bucket"])
    if usable and detector_open_ids is not None and \
            set(detector_open_ids) != {e["episode_id"] for e in (state.get("open") or {}).values()}:
        usable = False       # never show projection details that disagree with the detector
    active = sorted(((state or {}).get("open") or {}).values(), key=_display_key) if usable else []
    last = None
    if usable and not active:
        ended = [e for e in (state.get("last_ended") or {}).values() if e.get("terminal_at")]
        retention = timedelta(minutes=cfg.section("context")["last_event_retention_min"])
        ended = [e for e in ended if now - _ts(e["terminal_at"]) <= retention]
        if ended:
            last = max(ended, key=lambda e: (_ts(e["terminal_at"]), -EVENT_TYPES.index(e["event_type"])))
    stale = product["status"] == "DATA STALE"
    from .readiness import headline as readiness_headline
    return {
        "headline": readiness_headline(product["status"], readiness), "product_status": product["status"],
        "readiness": None if stale else (dict(readiness) if readiness is not None else None),
        "status_reasons": list(product.get("reasons") or []), "requested_at": iso(now),
        "as_of_bucket": state["as_of_bucket"] if usable else None,
        "data_through": iso(_ts(state["as_of_bucket"]) + BUCKET) if usable else None,
        "projection_available": usable,
        "active_episode": active[0] if active else None,
        "other_active": [[e["event_type"], e["state"]] for e in active[1:]],
        "last_event": last,
        "now": state.get("now") if usable and not stale else None,
        "context_1h": state.get("context_1h") if usable and not stale else None,
        "episodization_version": (state or {}).get("episodization_version"),
        "episodization_digest": (state or {}).get("episodization_digest"),
        "live_hysteresis_enabled": False,
        "context_version": (state or {}).get("context_version"),
        "context_state_digest": state_digest_value if usable else None,
        # Presentation projection (1h time-of-day baseline). Language-neutral. Not detection.
        "horizons": None if horizons is None else dict(horizons),
    }


def find_episode(state: Optional[Mapping[str, Any]], episode_id: str) -> Optional[dict]:
    for e in list(((state or {}).get("open") or {}).values()) + \
            list(((state or {}).get("last_ended") or {}).values()):
        if e["episode_id"] == episode_id:
            return e
    return None
