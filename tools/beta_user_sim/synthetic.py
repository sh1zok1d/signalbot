"""Fully synthetic replay bundle, built with the production beta pipeline.

Nothing here is market data. A deterministic synthetic 1m price path drives
synthetic 5m tape snapshots; the REAL rule evaluation (`evaluate_bucket`),
detector state machine (`step_episode`), push policy (`push_policy`), context
projection (`step_context`), /btc view model (`btc_view`), renderer
(`format_btc`) and outcome function (`compute_outcome`) turn them into the same
row shapes an export of the beta tables would contain. Dates are in 2024 on
purpose: no protected 2025/2026 period is represented, even synthetically.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
import statistics
from datetime import datetime, timedelta, timezone
from typing import Optional

from beta import context as cx
from beta.config import EVENT_TYPES, BetaConfig
from beta.detector import BucketContext, push_policy, step_episode
from beta.formatter import format_btc
from beta.horizons import HORIZON_VERSION, verify_horizon_digest
from beta.models import TRIGGERED
from beta.outcomes import LAST_BAR_GRACE, compute_outcome, outcome_digest
from beta.readiness import readiness
from beta.rules import evaluate_bucket
from beta.state_tape import BUCKET, metric_key, sha256_json

from .bundle import BUNDLE_VERSION, PROVENANCE_SYNTHETIC, canonical

SYN_T0 = datetime(2024, 3, 4, 8, 0, tzinfo=timezone.utc)
SYN_BUCKETS = 96
_CALC = "s" * 16
_NEUTRAL = {"price": 0.5, "oi": 0.5, "range": 0.5, "volume": 0.5, "taker": 0.5}
# Scripted rank regimes per bucket index (synthetic; chosen so real rules fire).
_DOWN = {"price": 0.02, "oi": 0.05}
_TAKER_BUY = {"taker": 0.995}
_BUILDUP = {"range": 0.2, "oi": 0.9, "volume": 0.7}


def _v02_push_cfg(cfg: BetaConfig) -> BetaConfig:
    """The harness replays the V0.2 event push (`format_push_v02`), so its synthetic
    decisions use the V0.2 delivery policy: 3 a day, no global cooldown, no quiet
    hours. The unusual-hour gate itself is answered by `hour={"qualified": True}`."""
    return cfg.with_overrides(max_new_pushes_per_utc_day=3,
                              push_policy={"quiet_hours_kyiv": ["00:00", "00:00"], "global_cooldown_min": 1})


def _regime(i: int) -> dict:
    if 14 <= i <= 17:
        return _DOWN
    if 40 <= i <= 42:
        return _TAKER_BUY
    if 60 <= i <= 63:
        return _DOWN
    if 66 <= i <= 67:
        return _DOWN
    if 80 <= i <= 90:
        return _BUILDUP
    return {}


def _price(minute: float) -> float:
    """Synthetic composite price path (USD). Deterministic, smooth, with scripted moves."""
    base = 64_000.0 + 180.0 * math.sin(minute / 47.0) + 60.0 * math.sin(minute / 9.0)
    drop = -420.0 / (1.0 + math.exp(-(minute - 80.0) / 6.0))
    pop = 260.0 / (1.0 + math.exp(-(minute - 205.0) / 5.0))
    drop2 = -300.0 / (1.0 + math.exp(-(minute - 310.0) / 7.0))
    return base + drop + pop + drop2


def _venue_offsets(cfg: BetaConfig) -> dict:
    return {ex: (i - 1) * 3.0 for i, ex in enumerate(cfg.exchanges)}


def _klines(cfg: BetaConfig, start: datetime, end: datetime) -> list:
    out, off = [], _venue_offsets(cfg)
    m = start
    while m < end:
        x = (m - SYN_T0).total_seconds() / 60.0
        o, c = _price(x), _price(x + 1.0)
        hi = max(o, c) + 6.0 + 4.0 * abs(math.sin(x / 3.0))
        lo = min(o, c) - 6.0 - 4.0 * abs(math.cos(x / 5.0))
        for ex in cfg.exchanges:
            d = off[ex]
            out.append({"exchange": ex, "ts": m, "open": o + d, "high": hi + d, "low": lo + d, "close": c + d})
        m += timedelta(minutes=1)
    return out


def _snap(cfg: BetaConfig, ranks: dict, bucket: datetime) -> dict:
    """Synthetic LIVE-like tape snapshot with mature percentiles (shape of the beta tape)."""
    r = {**_NEUTRAL, **ranks}
    x0 = (bucket - SYN_T0).total_seconds() / 60.0
    p0, p1 = _price(x0), _price(x0 + 5.0)
    v = {"price": (p1 / p0 - 1.0) * 100.0 if not ranks.get("price") else (r["price"] - 0.5) * 2,
         "oi": (r["oi"] - 0.5) * 4, "range": 0.1 + r["range"] * 0.3,
         "volume": 1e8 * (1 + r["volume"]), "taker": (r["taker"] - 0.5) * 1e7}
    keys = {"price": "c:price_move_pct_median", "oi": "c:oi_change_pct_median",
            "range": "c:range_width_pct_median", "volume": "c:volume_notional_usd_sum",
            "taker": "c:taker_delta_notional_usd_sum"}
    metrics = {keys[k]: v[k] for k in keys}
    pct = {keys[k]: {"value": v[k], "rank": r[k], "tier": "mature"} for k in keys}
    raw = {ex: {"price_move_pct": v["price"], "oi_change_pct": v["oi"], "taker_delta_notional_usd": v["taker"],
                "range_width_pct": v["range"], "volume_notional_usd": v["volume"] / 3} for ex in cfg.exchanges}
    for ex in cfg.exchanges:
        for side in ("long_liquidation_notional", "short_liquidation_notional"):
            metrics[metric_key(ex, side)] = 1e5
            pct[metric_key(ex, side)] = {"value": 1e5, "rank": 0.5, "tier": "mature"}
    fam = {"available": 3, "expected": 3, "contributing": list(cfg.exchanges), "usable": True}
    closes = [_price(x0 + 5.0) + d for d in _venue_offsets(cfg).values()]
    return {"materialized": True, "evaluation_fresh": True, "stale_barrier": False,
            "identity": {"calculation_version": _CALC}, "code_version": "synthetic",
            "state_schema_version": cfg.state_schema_version,
            "metrics": metrics, "percentiles": pct, "venue_raw": raw,
            "families": {f: dict(fam) for f in ("price_structure", "oi", "volume", "taker_flow")},
            "venues": {ex: {"declared_available": True, "heartbeat_healthy": True} for ex in cfg.exchanges},
            "reference": {"status": "OK", "price": float(statistics.median(closes)),
                          "exchanges": list(cfg.exchanges), "dispersion_pct": 0.01}}


def _window_stats(end: datetime, minutes: int) -> dict:
    x1 = (end - SYN_T0).total_seconds() / 60.0
    x0 = x1 - minutes
    xs = [x0 + k for k in range(minutes + 1)]
    ps = [_price(x) for x in xs]
    return {"move": (ps[-1] / ps[0] - 1.0) * 100.0, "range": (max(ps) - min(ps)) / ps[0] * 100.0,
            "high": max(ps), "low": min(ps)}


def _horizons(cfg: BetaConfig, through: datetime, i: int) -> dict:
    """Language-neutral horizon blocks with the production key set, from the synthetic path."""
    h1, h24 = _window_stats(through, 60), _window_stats(through, 1440)
    vol_ratio = 1.0 + 0.6 * abs(math.sin(i / 7.0)) + (0.9 if _regime(i) else 0.0)
    nolq = {ex: {"long": {"amount": 2e5, "missing": False, "lower_bound": ex == "binance"},
                 "short": {"amount": 1e5, "missing": False, "lower_bound": ex == "binance"}}
            for ex in cfg.exchanges}
    days = {"range_width_pct_median": 30, "price_move_pct_median": 30, "volume_notional_usd_sum": 30}
    return {
        "version": HORIZON_VERSION, "digest": verify_horizon_digest(),
        "1h": {"complete": True, "window_start": cx.iso(through - timedelta(hours=1)), "window_end": cx.iso(through),
               "price_move_pct": h1["move"], "range_width_pct": h1["range"],
               "volume_notional_usd": 1.2e9 * vol_ratio, "baseline_days": days,
               "baseline_median": {"range_width_pct_median": h1["range"] / 1.1, "price_move_pct_median": 0.0,
                                   "volume_notional_usd_sum": 1.2e9},
               "range_ratio": 1.1, "volume_ratio": vol_ratio, "taker_delta_notional_usd_sum": 2.0e7,
               "funding_rate": 0.00006, "oi_change_pct": 0.4 if i % 2 else -0.3,
               "oi_by_venue": {ex: 0.4 if i % 2 else -0.3 for ex in cfg.exchanges},
               "liquidations": {"buckets_missing": False, "venues": nolq}},
        "24h": {"price_complete": True, "volume_complete": True, "volume_partial": False,
                "buckets_present": 288, "buckets_expected": 288,
                "window_start": cx.iso(through - timedelta(hours=24)), "window_end": cx.iso(through),
                "price_move_pct": h24["move"], "range_width_pct": h24["range"],
                "high": h24["high"], "low": h24["low"], "volume_notional_usd": 2.6e10,
                "baseline_days": {"range_width_pct": 30, "price_move_pct": 30, "volume_notional_usd": 30},
                "baseline_median": {"range_width_pct": h24["range"], "price_move_pct": 0.0,
                                    "volume_notional_usd": 2.9e10},
                "range_ratio": 1.0, "volume_ratio": 0.9, "taker_delta_notional_usd_sum": -4.0e7,
                "funding_rate": 0.00006, "funding_rate_avg": 0.00005, "oi_change_pct": 1.2,
                "oi_by_venue": {ex: 1.2 for ex in cfg.exchanges},
                "liquidations": {"buckets_missing": False, "venues": nolq}, "changes": []},
    }


def _digest(i: int, salt: str) -> str:
    return hashlib.sha256(f"{salt}:{i}".encode()).hexdigest()


def make_synthetic_bundle(cfg: BetaConfig, *, langs: tuple = ("ru", "en"), buckets: int = SYN_BUCKETS) -> dict:
    t0 = SYN_T0
    rows, prev = {}, None
    for i in range(buckets):
        b = t0 + i * BUCKET
        s = _snap(cfg, _regime(i), b)
        s["rule_evaluations"] = evaluate_bucket(cfg, s, prev)
        prev = s["rule_evaluations"]
        rows[b] = {"tape_id": i + 1, "revision": 1, "snapshot_digest": _digest(i, "tape"), "snapshot": s}
    states = cx.replay(cfg, rows, start_bucket=t0, end_bucket=t0 + (buckets - 1) * BUCKET)

    episodes, transitions, decisions, deliveries = {}, [], [], []
    open_, pk_of, seq_of = {}, {}, {}
    last_terminal, last_would, per_day = {}, {}, {}

    def _record(pid: str, frm, to, b, reason, digest):
        seq_of[pid] = seq_of.get(pid, 0) + 1
        transitions.append({"episode_pk": pk_of[pid], "seq": seq_of[pid], "from_state": frm, "to_state": to,
                            "decision_bucket": b, "decision_ts": b + BUCKET, "snapshot_digest": digest,
                            "reason": reason, "recorded_at": b + BUCKET + timedelta(seconds=3)})

    for i in range(buckets):
        b = t0 + i * BUCKET
        row = rows[b]
        s = row["snapshot"]
        ctx = BucketContext(bucket_ts=b, decision_ts=b + BUCKET, snapshot_digest=row["snapshot_digest"],
                            calculation_version=_CALC, reference=s["reference"], code_version="synthetic")
        for et in EVENT_TYPES:
            st = step_episode(cfg, et, open_.get(et), s["rule_evaluations"][et], ctx)
            if st.terminated is not None:
                ep = st.terminated
                episodes[ep.public_id] = ep
                _record(ep.public_id, st.terminated_from, ep.state, b, ep.terminal_reason, ctx.snapshot_digest)
                last_terminal[et] = ep.terminal_at
                open_.pop(et, None)
            if st.updated is not None:
                ep = st.updated
                episodes[ep.public_id] = ep
                open_[et] = ep
                for which, frm, to, reason in st.transitions:
                    if which == "updated":
                        _record(ep.public_id, frm, to, b, reason, ctx.snapshot_digest)
            if st.opened is not None:
                ep = st.opened
                pk_of[ep.public_id] = len(pk_of) + 1
                episodes[ep.public_id] = ep
                open_[et] = ep
                _record(ep.public_id, None, ep.state, b, "CONDITION_MET", ctx.snapshot_digest)
            if st.triggered is not None:
                ep = open_[et]
                evaluated = ctx.decision_ts + timedelta(seconds=10)
                day = ctx.decision_ts.date()
                would, decision, reason = push_policy(
                    _v02_push_cfg(cfg), decision_ts=ctx.decision_ts, evaluated_at=evaluated, snapshot=s,
                    last_same_type_terminal=last_terminal.get(et), last_same_type_would_push=last_would.get(et),
                    would_push_today=per_day.get(day, 0), push_enabled=True,
                    hour={"qualified": True})      # synthetic tape: no 1h ranks; treat every hour as qualified
                if would:
                    per_day[day] = per_day.get(day, 0) + 1
                    last_would[et] = ctx.decision_ts
                pk = pk_of[ep.public_id]
                decisions.append({"episode_pk": pk, "event_type": et, "decision_ts": ctx.decision_ts,
                                  "utc_day": day.isoformat(), "would_push": would, "decision": decision,
                                  "suppression_reason": reason, "push_enabled_effective": True,
                                  "recorded_at": evaluated})
                if decision == "PUSH":
                    deliveries.append({"episode_pk": pk, "state": "SENT", "suppression_reason": None,
                                       "decision_ts": ctx.decision_ts,
                                       "created_at": evaluated + timedelta(seconds=1),
                                       "sending_at": evaluated + timedelta(seconds=2),
                                       "finished_at": evaluated + timedelta(seconds=4), "error_summary": None})

    end = t0 + buckets * BUCKET
    klines = _klines(cfg, t0, end + timedelta(hours=24, minutes=5))
    ep_rows, outcomes = [], []
    for pid, ep in sorted(episodes.items(), key=lambda kv: pk_of[kv[0]]):
        pk = pk_of[pid]
        d = {"episode_pk": pk, "public_id": pid, "symbol": ep.symbol, "event_type": ep.event_type,
             "state": ep.state, "opened_bucket": ep.opened_bucket, "opened_at": ep.opened_at,
             "armed_at": ep.armed_at, "triggered_at": ep.triggered_at, "terminal_at": ep.terminal_at,
             "terminal_reason": ep.terminal_reason, "rules_version": ep.rules_version,
             "rules_digest": ep.rules_digest, "code_version": ep.code_version,
             "calculation_version": ep.calculation_version, "opening_tape_digest": ep.opening_tape_digest,
             "trigger_tape_digest": ep.trigger_tape_digest, "last_bucket": ep.last_bucket,
             "last_streak": ep.last_streak, "reference_price": ep.reference_price,
             "reference_exchanges": list(ep.reference_exchanges),
             "reference_dispersion_pct": ep.reference_dispersion_pct, "reference_bucket": ep.reference_bucket,
             "correction_flag": False, "correction_note": None}
        ep_rows.append(d)
        if ep.triggered_at is None:
            continue
        for h in cfg.horizons:
            o = compute_outcome(anchor=ep.triggered_at, horizon=h, reference_price=ep.reference_price,
                                exchanges=list(ep.reference_exchanges), klines=klines)
            outcomes.append({**o, "episode_pk": pk, "horizon": h, "outcome_version": cfg.outcome_version,
                             "revision": 1, "supersedes_outcome_id": None, "source_raw_revision": None,
                             "outcome_digest": outcome_digest(o),
                             "computed_at": o["window_end"] + LAST_BAR_GRACE + timedelta(minutes=1)})

    views, view_pk = [], 0
    for i in range(buckets):
        b = t0 + i * BUCKET
        triggered_here = any(tr["to_state"] == TRIGGERED and tr["decision_bucket"] == b for tr in transitions)
        offsets = []
        if i % 6 == 5:
            offsets.append(timedelta(seconds=40))
        if triggered_here:
            offsets.append(timedelta(seconds=95))
        for off in offsets:
            now = b + BUCKET + off
            state = states[i]
            opn = [e["state"] for e in (state.get("open") or {}).values()]
            status = "EVENT ACTIVE" if "TRIGGERED" in opn else "WATCH" if opn else "NO ACTIVE EVENTS"
            product = {"status": status, "reasons": [], "last_good_bucket": b}
            rd = readiness(cfg, {"bucket_ts": b, "snapshot": rows[b]["snapshot"]}, maturity_days=30.0)
            view = btc_view_payload(cfg, product=product, state=state, now=now, readiness=rd,
                                    open_ids=[e["episode_id"] for e in (state.get("open") or {}).values()],
                                    horizons=_horizons(cfg, b + BUCKET, i))
            for k, lang in enumerate(langs):
                if lang != langs[0] and i % 12 != 5:
                    continue
                view_pk += 1
                html = format_btc(cfg, view, lang)
                views.append({"view_pk": view_pk, "requested_at": now + timedelta(milliseconds=k),
                              "as_of_bucket": b, "context_state_digest": view["context_state_digest"],
                              "episodization_version": view["episodization_version"],
                              "episodization_digest": view["episodization_digest"],
                              "payload": copy.deepcopy(view), "payload_digest": sha256_json(view),
                              "rendered_sha256": hashlib.sha256(html.encode("utf-8")).hexdigest(),
                              "rendered_html": html, "lang": lang,
                              "recorded_at": now + timedelta(milliseconds=k)})

    raw = {"bundle_version": BUNDLE_VERSION, "provenance": PROVENANCE_SYNTHETIC, "symbol": cfg.symbol,
           "exported_at": end + timedelta(hours=24, minutes=10), "btc_views": views, "episodes": ep_rows,
           "transitions": transitions, "push_decisions": decisions, "deliveries": deliveries,
           "outcomes": outcomes, "klines": klines}
    return json.loads(canonical(raw))


def btc_view_payload(cfg: BetaConfig, *, product: dict, state: dict, now: datetime, readiness: Optional[dict],
                     open_ids: list, horizons: dict) -> dict:
    view = cx.btc_view(cfg, product=product, state=state, state_digest_value=cx.state_digest(state), now=now,
                       readiness=readiness, detector_open_ids=open_ids, horizons=horizons)
    return json.loads(canonical(view))
