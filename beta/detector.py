"""Beta V0.2 detector: episode state machine, push policy, and bucket runners.

State machine (pure): `step_episode` maps (open episode, this bucket's rule
evaluation) -> transitions. Lifecycle states EARLY/ARMED/TRIGGERED/ENDED/EXPIRED;
NOT_EVALUABLE is only an evaluation result (it terminalizes an open episode,
fail-closed). Streak-based entry: a new episode opens only when the consecutive
qualifying streak EQUALS the entry streak, so MAX_DURATION cannot immediately
re-open the same run.

Runner: one closed 5m bucket = ONE PostgreSQL transaction (LIVE tape row +
episode transitions + push decisions + watermark), under the detector advisory
lock. A crash before commit leaves nothing; a re-run reprocesses the bucket.
The frozen V1/V2 forecast engines are never imported or called.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping, Optional, Sequence

from .config import (BetaConfig, BetaSwitches, EVENT_TYPES, LIQUIDATION_STRESS_LONG,
                     LIQUIDATION_STRESS_SHORT, POSITION_BUILDUP_COMPRESSION,
                     PRICE_OI_CONTRACTION_DOWN, PRICE_OI_CONTRACTION_UP,
                     TAKER_FLOW_EXTREME_BUY, TAKER_FLOW_EXTREME_SELL, effective_push_enabled)
from .models import (ARMED, CORE_FAMILIES, DAILY_CAP, DATA_DEGRADED_REASON, DELIVERY_TOO_OLD,
                     EARLY, ENDED, EXPIRED, Episode, GLOBAL_COOLDOWN, HOUR_NOT_UNUSUAL,
                     NOT_EVALUABLE, ORIGIN_BOOTSTRAP, QUIET_HOURS,
                     ORIGIN_CORRECTION_CHECK, ORIGIN_LIVE, PUSH, PUSH_DISABLED, QUALIFIES,
                     REASON_CONDITION_FAILED, REASON_CONDITION_MET, REASON_DETECTION_GAP,
                     REASON_DETECTOR_VERSION_CHANGED, REASON_MAX_DURATION, REASON_NOT_EVALUABLE,
                     SAME_EVENT_COOLDOWN, STATE_ORDER, SUPPRESSED, TRIGGERED)
from .health import venue_states
from .rules import evaluate_bucket
from .state_tape import (BUCKET, PERCENTILE_HISTORY_SCHEMA_VERSIONS, build_tape_record,
                         carries_temporal_context, compute_percentiles, extract_metrics,
                         history_window, materialize_bucket, percentile_inputs,
                         select_latest_closed_bucket, with_rule_evaluations)

DETECTOR = "detector"
BOOTSTRAP = "bootstrap"


# ---- lifecycle thresholds per event type (from config) -----------------------
@dataclass(frozen=True)
class Lifecycle:
    entry_streak: int
    entry_state: str
    armed_at: Optional[int]
    triggered_at: int
    max_duration: Optional[timedelta]


def lifecycle(cfg: BetaConfig, event_type: str) -> Lifecycle:
    if event_type in (PRICE_OI_CONTRACTION_DOWN, PRICE_OI_CONTRACTION_UP):
        r = cfg.rule(event_type)
        return Lifecycle(r["armed_at_streak"], ARMED, r["armed_at_streak"], r["triggered_at_streak"], None)
    if event_type == POSITION_BUILDUP_COMPRESSION:
        r = cfg.rule(event_type)
        return Lifecycle(r["early_at_streak"], EARLY, r["armed_at_streak"], r["triggered_at_streak"],
                         timedelta(minutes=r["max_duration_min"]))
    if event_type in (TAKER_FLOW_EXTREME_BUY, TAKER_FLOW_EXTREME_SELL):
        r = cfg.rule("TAKER_FLOW_EXTREME")
        return Lifecycle(r["armed_at_streak"], ARMED, r["armed_at_streak"], r["triggered_at_streak"], None)
    if event_type in (LIQUIDATION_STRESS_LONG, LIQUIDATION_STRESS_SHORT):
        r = cfg.rule("LIQUIDATION_STRESS")
        return Lifecycle(r["triggered_at_streak"], TRIGGERED, None, r["triggered_at_streak"], None)
    raise ValueError(f"unknown event type {event_type!r}")


def public_episode_id(symbol: str, event_type: str, opened_bucket: datetime, rules_digest: str) -> str:
    """Deterministic, assigned ONCE at creation from the opening identity (never
    recomputed from corrected data)."""
    raw = f"{symbol}|{event_type}|{opened_bucket.isoformat()}|{rules_digest}".encode("utf-8")
    return "EV-" + hashlib.sha256(raw).hexdigest()[:10].upper()


@dataclass(frozen=True)
class BucketContext:
    bucket_ts: datetime
    decision_ts: datetime
    snapshot_digest: str
    calculation_version: str
    reference: Mapping[str, Any]
    code_version: str


@dataclass
class Step:
    """Planned changes for ONE event type in ONE bucket."""
    terminated: Optional[Episode] = None          # updated terminal episode
    terminated_from: Optional[str] = None
    updated: Optional[Episode] = None             # updated still-open episode
    updated_from: Optional[str] = None
    opened: Optional[Episode] = None              # new episode (not yet persisted)
    transitions: list = field(default_factory=list)   # (which, from, to, reason)
    triggered: Optional[str] = None               # 'updated' | 'opened' when TRIGGERED now


def _terminal(ep: Episode, ctx: BucketContext, reason: str) -> Episode:
    state = ENDED if ep.triggered_at is not None else EXPIRED
    return replace(ep, state=state, terminal_at=ctx.decision_ts, terminal_reason=reason)


def _with_reference(ep: Episode, ctx: BucketContext) -> Episode:
    ref = ctx.reference or {}
    if ref.get("status") != "OK":
        return replace(ep, reference_price=None, reference_exchanges=tuple(ref.get("exchanges") or ()),
                       reference_dispersion_pct=None, reference_bucket=ctx.bucket_ts)
    return replace(ep, reference_price=float(ref["price"]), reference_exchanges=tuple(ref["exchanges"]),
                   reference_dispersion_pct=float(ref["dispersion_pct"]), reference_bucket=ctx.bucket_ts)


def step_episode(cfg: BetaConfig, event_type: str, open_ep: Optional[Episode],
                 ev: Mapping[str, Any], ctx: BucketContext) -> Step:
    lc = lifecycle(cfg, event_type)
    step = Step()
    status, streak = ev["status"], int(ev["streak"])

    if open_ep is not None:
        reason = None
        if open_ep.rules_digest != cfg.rules_digest or (
                ctx.calculation_version != "UNMATERIALIZED"
                and open_ep.calculation_version != ctx.calculation_version):
            reason = REASON_DETECTOR_VERSION_CHANGED
        elif ctx.bucket_ts != open_ep.last_bucket + BUCKET:
            reason = REASON_DETECTION_GAP
        elif status == NOT_EVALUABLE:
            reason = REASON_NOT_EVALUABLE
        elif status != QUALIFIES:
            reason = REASON_CONDITION_FAILED
        elif streak != open_ep.last_streak + 1:
            reason = REASON_DETECTION_GAP
        elif lc.max_duration is not None and ctx.decision_ts - open_ep.opened_at >= lc.max_duration:
            reason = REASON_MAX_DURATION
        if reason is not None:
            done = _terminal(open_ep, ctx, reason)
            step.terminated, step.terminated_from = done, open_ep.state
            step.transitions.append(("terminated", open_ep.state, done.state, reason))
        else:
            ep = replace(open_ep, last_bucket=ctx.bucket_ts, last_streak=streak)
            cur = open_ep.state
            if lc.armed_at is not None and STATE_ORDER[cur] < STATE_ORDER[ARMED] and streak >= lc.armed_at:
                ep = replace(ep, state=ARMED, armed_at=ctx.decision_ts)
                step.transitions.append(("updated", cur, ARMED, REASON_CONDITION_MET))
                cur = ARMED
            if STATE_ORDER[cur] < STATE_ORDER[TRIGGERED] and streak >= lc.triggered_at:
                ep = _with_reference(replace(ep, state=TRIGGERED, triggered_at=ctx.decision_ts,
                                             trigger_tape_digest=ctx.snapshot_digest), ctx)
                step.transitions.append(("updated", cur, TRIGGERED, REASON_CONDITION_MET))
                step.triggered = "updated"
            step.updated, step.updated_from = ep, open_ep.state
            return step

    # Entry (no open episode, or the previous one terminated in this bucket).
    if status == QUALIFIES and streak == lc.entry_streak:
        state = lc.entry_state
        ep = Episode(
            episode_pk=None,
            public_id=public_episode_id(cfg.symbol, event_type, ctx.bucket_ts, cfg.rules_digest),
            symbol=cfg.symbol, event_type=event_type, state=state, opened_bucket=ctx.bucket_ts,
            opened_at=ctx.decision_ts,
            armed_at=ctx.decision_ts if state in (ARMED, TRIGGERED) and lc.armed_at is not None else None,
            triggered_at=ctx.decision_ts if state == TRIGGERED else None,
            terminal_at=None, terminal_reason=None, rules_version=cfg.rules_version,
            rules_digest=cfg.rules_digest, code_version=ctx.code_version,
            calculation_version=ctx.calculation_version, opening_tape_digest=ctx.snapshot_digest,
            trigger_tape_digest=ctx.snapshot_digest if state == TRIGGERED else None,
            last_bucket=ctx.bucket_ts, last_streak=streak)
        if state == TRIGGERED:
            ep = _with_reference(ep, ctx)
            step.triggered = "opened"
        step.opened = ep
        step.transitions.append(("opened", None, state, REASON_CONDITION_MET))
    return step


# ---- push policy (pure) ------------------------------------------------------
def in_quiet_hours(cfg: BetaConfig, decision_ts: datetime) -> bool:
    """Kyiv wall-clock quiet window [start, end), wrapping midnight when start > end."""
    from .i18n import KYIV
    start, end = cfg.quiet_hours_kyiv
    local = decision_ts.astimezone(KYIV)
    now_m = local.hour * 60 + local.minute
    s = int(start[:2]) * 60 + int(start[3:])
    e = int(end[:2]) * 60 + int(end[3:])
    if s == e:
        return False
    return (s <= now_m < e) if s < e else (now_m >= s or now_m < e)


def push_policy(cfg: BetaConfig, *, decision_ts: datetime, evaluated_at: datetime,
                snapshot: Mapping[str, Any], last_same_type_terminal: Optional[datetime],
                last_same_type_would_push: Optional[datetime], would_push_today: int,
                push_enabled: bool, hour: Optional[Mapping[str, Any]] = None,
                last_any_would_push: Optional[datetime] = None) -> tuple:
    """(would_push, decision, suppression_reason). Evaluated in a fixed order;
    `would_push` means every gate except PUSH_DISABLED passed (the daily cap
    counts would-push decisions so a push-disabled soak still measures it).

    `hour` is the product-level unusual-hour gate (`beta.hour_gate.evaluate_hour`) of
    the rolling 1h around this decision; an absent or unqualified hour never pushes
    (`HOUR_NOT_UNUSUAL`). Every reason after it implies the hour qualified
    (PRODUCT_FIRST_DECISION_V1 §3.1b.3)."""
    from .hour_gate import is_qualified
    fams = snapshot.get("families") or {}
    if not snapshot.get("evaluation_fresh") or not all((fams.get(f) or {}).get("usable")
                                                       for f in CORE_FAMILIES):
        return False, SUPPRESSED, DATA_DEGRADED_REASON
    if evaluated_at - decision_ts > cfg.delivery_ttl:
        return False, SUPPRESSED, DELIVERY_TOO_OLD
    if not is_qualified(hour):
        return False, SUPPRESSED, HOUR_NOT_UNUSUAL
    for last in (last_same_type_terminal, last_same_type_would_push):
        if last is not None and decision_ts - last < cfg.cooldown:
            return False, SUPPRESSED, SAME_EVENT_COOLDOWN
    if last_any_would_push is not None and decision_ts - last_any_would_push < cfg.global_cooldown:
        return False, SUPPRESSED, GLOBAL_COOLDOWN
    if in_quiet_hours(cfg, decision_ts):
        return False, SUPPRESSED, QUIET_HOURS
    if would_push_today >= cfg["max_new_pushes_per_utc_day"]:
        return False, SUPPRESSED, DAILY_CAP
    if not push_enabled:
        return True, SUPPRESSED, PUSH_DISABLED
    return True, PUSH, None


# ---- runner ------------------------------------------------------------------
@dataclass(frozen=True)
class DetectorDeps:
    """Runtime collaborators (all injectable for offline tests).
    reader: RawBundleReader (Database); store: storage.beta_v0_store.BetaStore;
    declared_liquidation_available: async (exchanges) -> {ex: bool};
    raw_revision: async () -> Optional[int]; clock: () -> datetime."""
    reader: Any
    store: Any
    stage2_config: Any
    declared_liquidation_available: Any
    raw_revision: Any
    clock: Any
    code_version: str
    feature_code_version: str


async def _materialize(deps: DetectorDeps, cfg: BetaConfig, conn, bucket_ts: datetime):
    rows = await conn.fetch_venue_bucket_rows(
        exchanges=cfg.exchanges, symbol=cfg.symbol, bucket_start=bucket_ts,
        bucket_end=bucket_ts + BUCKET)
    declared = await deps.declared_liquidation_available(cfg.exchanges)
    venues = venue_states(cfg, rows, declared, bucket_ts)
    availability = {ex: bool(v["declared_available"] and v["heartbeat_healthy"]) for ex, v in venues.items()}
    before = await deps.raw_revision()
    result, error = None, None
    try:
        result = await materialize_bucket(
            deps.reader, deps.stage2_config, cfg, bucket_ts=bucket_ts,
            code_version=deps.feature_code_version,
            liquidation_feed_available_by_exchange=availability)
    except Exception as exc:  # noqa: BLE001 - fail closed: recorded as NOT materialized
        error = type(exc).__name__
    after = await deps.raw_revision()
    return result, error, venues, before, after


async def build_live_record(deps: DetectorDeps, cfg: BetaConfig, conn, bucket_ts: datetime,
                            *, origin: str = ORIGIN_LIVE, with_percentiles: bool = True):
    result, error, venues, before, after = await _materialize(deps, cfg, conn, bucket_ts)
    ident = percentile_inputs(result)
    percentiles = None
    if ident is not None and with_percentiles:
        start, end = history_window(bucket_ts, cfg)
        history = await conn.fetch_tape_history(
            symbol=cfg.symbol, market_type=cfg.market_type, timeframe=cfg.timeframe,
            calculation_version=ident["calculation_version"],
            state_schema_versions=PERCENTILE_HISTORY_SCHEMA_VERSIONS[cfg.state_schema_version],
            start=start, end=end)
        venue_ok = {ex: bool(v["declared_available"] and v["heartbeat_healthy"]) for ex, v in venues.items()}
        percentiles = compute_percentiles(
            deps.stage2_config, cfg, bucket_ts=bucket_ts,
            metrics=extract_metrics(result, cfg, venue_ok, venues), ident=ident,
            code_version=deps.feature_code_version, history=history)
    return build_tape_record(
        cfg, bucket_ts=bucket_ts, origin=origin, result=result, materialization_error=error,
        venues=venues, percentiles=percentiles, code_version=deps.code_version,
        feature_code_version=deps.feature_code_version, raw_revision_before=before,
        raw_revision_after=after, evaluated_at=deps.clock())


async def _apply_step(conn, cfg: BetaConfig, event_type: str, step: Step, ctx: BucketContext,
                      snapshot: Mapping[str, Any], evaluated_at: datetime, push_enabled: bool,
                      report: dict, hour_ctx: Optional[Mapping[str, Any]] = None) -> None:
    if step.terminated is not None:
        ep = step.terminated
        await conn.update_episode(ep, expected_state=step.terminated_from)
        seq = await conn.next_transition_seq(ep.episode_pk)
        await conn.insert_transition(
            episode_pk=ep.episode_pk, seq=seq, from_state=step.terminated_from, to_state=ep.state,
            decision_bucket=ctx.bucket_ts, decision_ts=ctx.decision_ts,
            snapshot_digest=ctx.snapshot_digest, reason=ep.terminal_reason)
        report["transitions"].append((ep.public_id, step.terminated_from, ep.state, ep.terminal_reason))
    target_pk, target = None, None
    if step.updated is not None:
        target = step.updated
        await conn.update_episode(target, expected_state=step.updated_from)
        target_pk = target.episode_pk
        for which, frm, to, reason in step.transitions:
            if which != "updated":
                continue
            seq = await conn.next_transition_seq(target_pk)
            await conn.insert_transition(
                episode_pk=target_pk, seq=seq, from_state=frm, to_state=to,
                decision_bucket=ctx.bucket_ts, decision_ts=ctx.decision_ts,
                snapshot_digest=ctx.snapshot_digest, reason=reason)
            report["transitions"].append((target.public_id, frm, to, reason))
    if step.opened is not None:
        target = step.opened
        target_pk = await conn.insert_episode(target)
        target = replace(target, episode_pk=target_pk)
        await conn.insert_transition(
            episode_pk=target_pk, seq=1, from_state=None, to_state=target.state,
            decision_bucket=ctx.bucket_ts, decision_ts=ctx.decision_ts,
            snapshot_digest=ctx.snapshot_digest, reason=REASON_CONDITION_MET)
        report["transitions"].append((target.public_id, None, target.state, REASON_CONDITION_MET))
    if step.triggered is not None:
        gate = await _hour_gate(conn, cfg, hour_ctx, snapshot)
        would, decision, reason = push_policy(
            cfg, decision_ts=ctx.decision_ts, evaluated_at=evaluated_at, snapshot=snapshot,
            last_same_type_terminal=await conn.latest_same_type_terminal(
                symbol=cfg.symbol, event_type=event_type, exclude_pk=target_pk),
            last_same_type_would_push=await conn.latest_same_type_would_push(
                event_type=event_type, exclude_pk=target_pk),
            would_push_today=await conn.count_would_push(ctx.decision_ts.date()),
            push_enabled=push_enabled, hour=gate,
            last_any_would_push=await conn.latest_any_would_push(exclude_pk=target_pk))
        await conn.insert_push_decision(
            episode_pk=target_pk, event_type=event_type, decision_ts=ctx.decision_ts,
            would_push=would, decision=decision, suppression_reason=reason,
            push_enabled_effective=push_enabled, gate=gate)
        report["push_decisions"].append((target.public_id, decision, reason))


async def _hour_gate(conn, cfg: BetaConfig, hour_ctx: Optional[Mapping[str, Any]],
                     snapshot: Mapping[str, Any]) -> dict:
    """The unusual-hour gate for this decision, from the rolling-1h reading computed
    for the same bucket and the liquidation-stress episodes reaching into that hour."""
    from .hour_gate import evaluate_hour
    liq = ()
    if hour_ctx and hour_ctx.get("window_start") and hour_ctx.get("window_end"):
        try:
            liq = await conn.fetch_liquidation_episodes(
                symbol=cfg.symbol, start=datetime.fromisoformat(hour_ctx["window_start"]),
                end=datetime.fromisoformat(hour_ctx["window_end"]))
        except Exception:  # noqa: BLE001 - evidence only; the gate degrades to "no flush"
            liq = ()
    return evaluate_hour(cfg, hour_ctx, liquidation_episodes=liq, snapshot=snapshot)


async def process_live_bucket(deps: DetectorDeps, cfg: BetaConfig, switches: BetaSwitches,
                              bucket_ts: datetime) -> dict:
    report = {"bucket_ts": bucket_ts, "transitions": [], "push_decisions": []}
    async with deps.store.connect() as conn:
        rec = await build_live_record(deps, cfg, conn, bucket_ts)
        prev = await conn.fetch_live_tape(symbol=cfg.symbol, bucket_ts=bucket_ts - BUCKET,
                                          rules_digest=cfg.rules_digest)
        previous = (prev["snapshot"] or {}).get("rule_evaluations") if prev else None
        evaluations = evaluate_bucket(cfg, rec.snapshot, previous)
        rec = with_rule_evaluations(cfg, rec, evaluations)
        ctx = BucketContext(bucket_ts=bucket_ts, decision_ts=bucket_ts + BUCKET,
                            snapshot_digest=rec.snapshot_digest,
                            calculation_version=rec.calculation_version,
                            reference=rec.snapshot["reference"], code_version=deps.code_version)
        context_state, context_error = None, None
        async with conn.transaction():
            tape_id = await conn.insert_tape(rec)
            # The rolling 1h/4h readings of THIS bucket, computed once before any push
            # decision (the unusual-hour gate needs the 1h reading) and reused by the
            # projection below. A failure here only means "no readable hour": detection
            # is unchanged and the projection recomputes in its own savepoint.
            try:
                bucket_ctx = await context_asof(cfg, deps.stage2_config, conn, bucket_ts, rec.snapshot, tape_id)
            except Exception as exc:  # noqa: BLE001 - isolated; the gate fails closed
                bucket_ctx, context_error = None, type(exc).__name__
            admin_push = await conn.get_admin_push_enabled()
            push_enabled = effective_push_enabled(switches, admin_push)
            open_eps = await conn.fetch_open_episodes(symbol=cfg.symbol)
            for et in EVENT_TYPES:
                step = step_episode(cfg, et, open_eps.get(et), evaluations[et], ctx)
                await _apply_step(conn, cfg, et, step, ctx, rec.snapshot, rec.evaluated_at,
                                  push_enabled, report, hour_ctx=(bucket_ctx or {}).get("1h"))
            await conn.advance_watermark(DETECTOR, symbol=cfg.symbol, market_type=cfg.market_type,
                                         timeframe=cfg.timeframe, bucket_ts=bucket_ts)
            # Presentation-only projection, AFTER every detector decision of this bucket
            # and in its own savepoint: it reads nothing the decisions depend on, and a
            # failure here can never roll back or alter detection (the next bucket
            # re-projects any bucket it missed from the LIVE rows).
            try:
                async with conn.transaction():
                    context_state = await advance_context(deps, cfg, conn, bucket_ts, rec, tape_id,
                                                          precomputed=bucket_ctx)
            except Exception as exc:  # noqa: BLE001 - isolated; reported, never raised
                context_error = type(exc).__name__
        report.update(materialized=rec.materialized, evaluation_fresh=rec.evaluation_fresh,
                      snapshot_digest=rec.snapshot_digest, context_error=context_error,
                      context={et: e["state"] for et, e in (context_state or {}).get("open", {}).items()},
                      evaluations={k: v["status"] for k, v in evaluations.items()})
    return report


# ---- temporal context (deterministic projection of the tape) -----------------
CONTEXT_MAX_GAP_BUCKETS = 8640          # > 30d without a state: restart empty


async def context_1h_asof(cfg: BetaConfig, stage2_config, conn, bucket_ts: datetime,
                          snapshot: Mapping[str, Any], tape_id: int) -> Optional[dict]:
    """Rolling-1h context for one bucket exactly as of its LIVE tape row."""
    return (await context_asof(cfg, stage2_config, conn, bucket_ts, snapshot, tape_id))["1h"]


async def context_asof(cfg: BetaConfig, stage2_config, conn, bucket_ts: datetime,
                       snapshot: Mapping[str, Any], tape_id: int) -> dict:
    """Rolling 1h and 4h context for one bucket exactly as of its LIVE tape row
    (history restricted to rows recorded before `tape_id`). One tape-history read
    and one Stage-1 OI range read serve both windows. A failed or absent OI read
    leaves only the OI value and rank missing."""
    from .context import CONTEXT_HORIZONS, context_1h, history_span
    none = {h: None for h in CONTEXT_HORIZONS}
    ident = snapshot.get("identity") or {}
    if not snapshot.get("materialized") or ident.get("calculation_version") in (None, "UNMATERIALIZED"):
        return none
    # The rolling windows need the V2 kline OHLC: only rows of THIS schema version (>= V2)
    # form a window; V1 rows are never mixed in (honest warm-up after an upgrade).
    if not carries_temporal_context(cfg.state_schema_version) or \
            snapshot.get("state_schema_version") != cfg.state_schema_version:
        return none
    span = history_span(cfg)
    history = await conn.fetch_tape_history(
        symbol=cfg.symbol, market_type=cfg.market_type, timeframe=cfg.timeframe,
        calculation_version=ident["calculation_version"], state_schema_versions=(cfg.state_schema_version,),
        start=bucket_ts - span, end=bucket_ts, before_tape_id=tape_id)
    oi_index = await _oi_index(cfg, conn, bucket_ts, span)
    tiers = stage2_config.resolve(cfg.symbol)["percentiles"]["confidence_tiers"]
    return {h: context_1h(cfg, bucket_ts=bucket_ts, current_metrics=snapshot.get("metrics") or {},
                          history=history, identity=ident, code_version=snapshot["feature_code_version"],
                          tiers=tiers, oi_index=oi_index, horizon=h)
            for h in CONTEXT_HORIZONS}


async def _oi_index(cfg: BetaConfig, conn, bucket_ts: datetime, span: timedelta):
    """Stage-1 OI rows covering every window boundary of the 30d ranks, as one index.
    Rows after the bucket's close are never read."""
    from .oi_asof import OI_ASOF_TOLERANCE, OiAsofIndex
    fetch = getattr(conn, "fetch_open_interest_range", None)
    if fetch is None:
        return None
    try:
        rows = await fetch(symbol=cfg.symbol, exchanges=list(cfg.exchanges),
                           start=bucket_ts - span - OI_ASOF_TOLERANCE, end=bucket_ts + BUCKET)
    except Exception:  # noqa: BLE001 - OI only; the other metrics are unaffected
        return None
    return OiAsofIndex(rows)


async def advance_context(deps: "DetectorDeps", cfg: BetaConfig, conn, bucket_ts: datetime,
                          rec, tape_id: int, precomputed: Optional[Mapping[str, Any]] = None) -> dict:
    """Advance the persisted context projection to `bucket_ts` (stepping through any
    buckets without a state first) and persist one state per bucket."""
    from .context import (adopt_predecessor_state, predecessor_context_digests, state_digest,
                          step_context, verify_versions)
    v = verify_versions(cfg)
    prev = await conn.fetch_latest_context_snapshot(
        symbol=cfg.symbol, before=bucket_ts, episodization_digest=v["episodization_digest"],
        context_digest=v["context_digest"], rules_digest=cfg.rules_digest)
    adopted = False
    if prev is None:
        # First bucket under a new context label: carry the episode memory of the
        # declared predecessor instead of restarting empty (open episodes would be lost).
        for old_digest in predecessor_context_digests(cfg):
            prev = await conn.fetch_latest_context_snapshot(
                symbol=cfg.symbol, before=bucket_ts, episodization_digest=v["episodization_digest"],
                context_digest=old_digest, rules_digest=cfg.rules_digest)
            if prev is not None:
                adopted = True
                break
    state, prev_digest, b = None, None, bucket_ts
    if prev is not None and int((bucket_ts - prev["bucket_ts"]) / BUCKET) <= CONTEXT_MAX_GAP_BUCKETS:
        state = adopt_predecessor_state(cfg, prev["state"]) if adopted else prev["state"]
        prev_digest, b = prev["state_digest"], prev["bucket_ts"] + BUCKET
    while b < bucket_ts:                               # buckets the projection has not seen
        row = await conn.fetch_live_tape(symbol=cfg.symbol, bucket_ts=b, rules_digest=cfg.rules_digest)
        ctx = {} if row is None else await context_asof(
            cfg, deps.stage2_config, conn, b, row["snapshot"], row["tape_id"])
        state = step_context(cfg, state, b, row, ctx.get("1h"), ctx.get("4h"))
        digest = state_digest(state)
        await conn.insert_context_snapshot(state, bucket_ts=b, tape_id=None if row is None else row["tape_id"],
                                           tape_revision=None if row is None else row["revision"],
                                           prev_state_digest=prev_digest, state_digest=digest)
        prev_digest, b = digest, b + BUCKET
    row = {"tape_id": tape_id, "revision": 1, "snapshot_digest": rec.snapshot_digest, "snapshot": rec.snapshot}
    ctx = precomputed if precomputed is not None else await context_asof(
        cfg, deps.stage2_config, conn, bucket_ts, rec.snapshot, tape_id)
    state = step_context(cfg, state, bucket_ts, row, ctx.get("1h"), ctx.get("4h"))
    digest = state_digest(state)
    await conn.insert_context_snapshot(state, bucket_ts=bucket_ts, tape_id=tape_id, tape_revision=1,
                                       prev_state_digest=prev_digest, state_digest=digest)
    return state


async def replay_context(cfg: BetaConfig, stage2_config, conn, *, start_bucket: datetime,
                         end_bucket: datetime, initial_state: Optional[Mapping[str, Any]] = None) -> list:
    """Recompute the projection from the LIVE tape rows (decision revisions) and the
    as-of 1h history, under the CONFIGURED episodization version."""
    from .context import replay
    rows = await conn.fetch_live_tape_range(symbol=cfg.symbol, start=start_bucket, end=end_bucket,
                                            rules_digest=cfg.rules_digest)
    ctx = {b: await context_asof(cfg, stage2_config, conn, b, r["snapshot"], r["tape_id"])
           for b, r in rows.items()}
    return replay(cfg, rows, start_bucket=start_bucket, end_bucket=end_bucket,
                  initial_state=initial_state,
                  context_1h_by_bucket={b: c["1h"] for b, c in ctx.items()},
                  context_4h_by_bucket={b: c["4h"] for b, c in ctx.items()})


def plan_buckets(watermark: Optional[datetime], target: datetime, max_catchup: int) -> tuple:
    """(buckets oldest-first, skipped_count). No watermark => only the target."""
    if watermark is None:
        return [target], 0
    first = watermark + BUCKET
    if first > target:
        return [], 0
    n = int((target - first) / BUCKET) + 1
    skipped = max(0, n - max_catchup)
    start = first + skipped * BUCKET
    return [start + i * BUCKET for i in range(n - skipped)], skipped


async def run_detector_once(deps: DetectorDeps, cfg: BetaConfig, switches: BetaSwitches, *,
                            explicit_bucket: Optional[datetime] = None) -> dict:
    now = deps.clock()
    if not switches.detection:
        return {"status": "DISABLED", "switches": switches.as_dict()}
    async with deps.store.advisory_lock(_detector_lock_key()) as acquired:
        if not acquired:
            return {"status": "LOCKED"}
        async with deps.store.connect() as conn:
            wm = await conn.get_watermark(DETECTOR, symbol=cfg.symbol, market_type=cfg.market_type,
                                          timeframe=cfg.timeframe)
        target = select_latest_closed_bucket(now, grace_s=cfg["bucket_close_grace_s"])
        if explicit_bucket is not None:
            if wm is not None and explicit_bucket <= wm:
                return await _correction_check(deps, cfg, explicit_bucket)
            if explicit_bucket > target:
                raise ValueError("explicit bucket is not closed yet")
            buckets, skipped = [explicit_bucket], 0
        else:
            buckets, skipped = plan_buckets(wm, target, cfg["detector"]["max_catchup_buckets_per_run"])
        reports = []
        for b in buckets:
            reports.append(await process_live_bucket(deps, cfg, switches, b))
        async with deps.store.connect() as conn:
            await conn.record_health(DETECTOR, now=deps.clock(), success=True,
                                     detail={"buckets": len(reports), "skipped": skipped})
        return {"status": "OK", "processed": reports, "skipped_buckets": skipped,
                "watermark_before": wm}


def _detector_lock_key() -> int:
    from storage.beta_v0_store import DETECTOR_LOCK_KEY
    return DETECTOR_LOCK_KEY


async def _correction_check(deps: DetectorDeps, cfg: BetaConfig, bucket_ts: datetime) -> dict:
    """Re-materialize an already-decided bucket. If its features changed, APPEND a
    CORRECTION_CHECK tape revision and annotate (never rewrite) affected episodes."""
    async with deps.store.connect() as conn:
        chain = await conn.fetch_bucket_chain(symbol=cfg.symbol, bucket_ts=bucket_ts, rules_digest=None)
        decided = [r for r in chain if r["origin"] in (ORIGIN_LIVE, ORIGIN_CORRECTION_CHECK)]
        # Compare like with like: only rows of the CURRENT rules digest AND state-tape
        # schema version share a correction identity (feature_digest).
        live = [r for r in decided if r["rules_digest"] == cfg.rules_digest
                and r["state_schema_version"] == cfg.state_schema_version]
        if not live:
            other = sorted({r["state_schema_version"] for r in decided} - {cfg.state_schema_version})
            if other:
                # A schema evolution is not a market-data correction: nothing is
                # appended and no episode is flagged.
                return {"status": "SCHEMA_VERSION_BOUNDARY", "bucket_ts": bucket_ts,
                        "stored_state_schema_versions": other,
                        "current_state_schema_version": cfg.state_schema_version}
            return {"status": "NO_LIVE_ROW_UNDER_CURRENT_RULES", "bucket_ts": bucket_ts}
        latest = live[-1]
        rec = await build_live_record(deps, cfg, conn, bucket_ts, origin=ORIGIN_CORRECTION_CHECK)
        if rec.calculation_version != latest["calculation_version"] or \
                rec.feature_digest == latest["feature_digest"]:
            return {"status": "UNCHANGED", "bucket_ts": bucket_ts,
                    "feature_digest": latest["feature_digest"]}
        revision = max(r["revision"] for r in live) + 1
        async with conn.transaction():
            tape_id = await conn.insert_tape(rec, revision=revision, supersedes_tape_id=latest["tape_id"])
            flagged = await conn.flag_correction(
                snapshot_digests=[r["snapshot_digest"] for r in live],
                note=f"input corrected: bucket {bucket_ts.isoformat()} revision {revision}")
        return {"status": "CORRECTION_APPENDED", "bucket_ts": bucket_ts, "tape_id": tape_id,
                "revision": revision, "episodes_flagged": flagged}


async def run_bootstrap_once(deps: DetectorDeps, cfg: BetaConfig, switches: BetaSwitches) -> dict:
    """Bounded, idempotent, oldest-first history materialization for mature 30d
    percentiles. Writes BOOTSTRAP tape rows only (no rules, no episodes, no
    forecasts, no Telegram). Skips buckets already on the tape."""
    if not switches.enabled:
        return {"status": "DISABLED", "switches": switches.as_dict()}
    now = deps.clock()
    target = select_latest_closed_bucket(now, grace_s=cfg["bucket_close_grace_s"])
    earliest = target - timedelta(days=cfg["bootstrap"]["lookback_days"])
    limit = cfg["bootstrap"]["max_buckets_per_run"]
    async with deps.store.advisory_lock(_detector_lock_key()) as acquired:
        if not acquired:
            return {"status": "LOCKED"}
        async with deps.store.connect() as conn:
            wm = await conn.get_watermark(BOOTSTRAP, symbol=cfg.symbol, market_type=cfg.market_type,
                                          timeframe=cfg.timeframe)
            b = max(earliest, wm + BUCKET) if wm is not None else earliest
            written = skipped = unmaterialized = 0
            last = None
            while b <= target and written + skipped < limit:
                if await conn.tape_bucket_exists(symbol=cfg.symbol, bucket_ts=b,
                                                 state_schema_version=cfg.state_schema_version):
                    skipped += 1
                else:
                    rec = await build_live_record(deps, cfg, conn, b, origin=ORIGIN_BOOTSTRAP,
                                                  with_percentiles=False)
                    async with conn.transaction():
                        await conn.insert_tape(rec)
                        await conn.advance_watermark(BOOTSTRAP, symbol=cfg.symbol,
                                                     market_type=cfg.market_type,
                                                     timeframe=cfg.timeframe, bucket_ts=b)
                    written += 1
                    unmaterialized += 0 if rec.materialized else 1
                last = b
                b += BUCKET
            if last is not None:
                await conn.advance_watermark(BOOTSTRAP, symbol=cfg.symbol, market_type=cfg.market_type,
                                             timeframe=cfg.timeframe, bucket_ts=last)
            await conn.record_health(BOOTSTRAP, now=deps.clock(), success=True,
                                     detail={"written": written, "skipped": skipped})
        return {"status": "OK" if b > target else "PARTIAL", "range_start": earliest,
                "target": target, "written": written, "skipped_existing": skipped,
                "unmaterialized": unmaterialized, "last_bucket": last, "complete": b > target}
